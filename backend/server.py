from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, date, timedelta
import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError
import csv
import json
import io
from collections import defaultdict
import calendar
import requests
import hmac
import hashlib

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT settings
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

# Slack settings - these should be set in environment variables
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN', '')
SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET', '')

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()

# User Models
class UserCreate(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    slack_user_id: Optional[str] = None
    slack_team_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    slack_user_id: Optional[str] = None
    created_at: datetime

# Habit Models
class HabitCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    habit_type: str  # "yes_no", "quantifiable", "time_based"
    target_value: Optional[float] = None  # For quantifiable/time_based habits
    target_unit: Optional[str] = None  # "minutes", "glasses", "pages", etc.
    frequency: str = "daily"  # "daily", "weekly", "custom"
    category: Optional[str] = None
    color: Optional[str] = "#8B5CF6"  # Default purple
    reminder_enabled: Optional[bool] = False
    reminder_time: Optional[str] = None  # HH:MM format
    slack_notifications: Optional[bool] = False

class HabitUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    reminder_enabled: Optional[bool] = None
    reminder_time: Optional[str] = None
    slack_notifications: Optional[bool] = None

class Habit(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    description: Optional[str] = ""
    habit_type: str
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    frequency: str = "daily"
    category: Optional[str] = None
    color: Optional[str] = "#8B5CF6"
    reminder_enabled: Optional[bool] = False
    reminder_time: Optional[str] = None
    slack_notifications: Optional[bool] = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

# Habit Record Models
class HabitRecordCreate(BaseModel):
    completed: bool = True
    value: Optional[float] = None  # For quantifiable habits
    notes: Optional[str] = ""

class HabitRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    habit_id: str
    date: date
    completed: bool = True
    value: Optional[float] = None
    notes: Optional[str] = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Import/Export Models
class ImportData(BaseModel):
    habits: List[Dict[str, Any]]
    records: Optional[List[Dict[str, Any]]] = []

# Slack Models
class SlackEventChallenge(BaseModel):
    challenge: str

class SlackUserUpdate(BaseModel):
    slack_user_id: str
    slack_team_id: Optional[str] = None

# Helper functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await db.users.find_one({"id": user_id})
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return User(**user)

def verify_slack_signature(timestamp: str, body: bytes, signature: str) -> bool:
    """Verify that the request is from Slack"""
    if not SLACK_SIGNING_SECRET:
        return True  # Skip verification if no secret is set
    
    request_hash = 'v0=' + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        f'v0:{timestamp}:{body.decode()}'.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(request_hash, signature)

async def send_slack_message(channel: str, text: str, blocks: Optional[List] = None):
    """Send a message to Slack"""
    if not SLACK_BOT_TOKEN:
        return {"ok": False, "error": "No Slack bot token configured"}
    
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "channel": channel,
        "text": text
    }
    
    if blocks:
        payload["blocks"] = blocks
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send Slack message: {e}")
        return {"ok": False, "error": str(e)}

# Authentication Routes
@api_router.post("/auth/register")
async def register(user_data: UserCreate):
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_password = hash_password(user_data.password)
    user = User(
        name=user_data.name,
        email=user_data.email
    )
    
    user_dict = user.dict()
    user_dict["password"] = hashed_password
    
    await db.users.insert_one(user_dict)
    
    # Create access token
    access_token = create_access_token(data={"sub": user.id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(**user.dict())
    }

@api_router.post("/auth/login")
async def login(login_data: UserLogin):
    user = await db.users.find_one({"email": login_data.email})
    if not user or not verify_password(login_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = create_access_token(data={"sub": user["id"]})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(**user)
    }

@api_router.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(**current_user.dict())

@api_router.post("/auth/slack/connect")
async def connect_slack(slack_data: SlackUserUpdate, current_user: User = Depends(get_current_user)):
    """Connect user's Slack account"""
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {
            "slack_user_id": slack_data.slack_user_id,
            "slack_team_id": slack_data.slack_team_id
        }}
    )
    
    return {"message": "Slack account connected successfully"}

# Habit Routes
@api_router.post("/habits", response_model=Habit)
async def create_habit(habit_data: HabitCreate, current_user: User = Depends(get_current_user)):
    habit = Habit(**habit_data.dict(), user_id=current_user.id)
    await db.habits.insert_one(habit.dict())
    return habit

@api_router.get("/habits", response_model=List[Habit])
async def get_habits(current_user: User = Depends(get_current_user)):
    habits = await db.habits.find({"user_id": current_user.id, "is_active": True}).to_list(1000)
    return [Habit(**habit) for habit in habits]

@api_router.get("/habits/{habit_id}", response_model=Habit)
async def get_habit(habit_id: str, current_user: User = Depends(get_current_user)):
    habit = await db.habits.find_one({"id": habit_id, "user_id": current_user.id})
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    return Habit(**habit)

@api_router.put("/habits/{habit_id}", response_model=Habit)
async def update_habit(habit_id: str, habit_data: HabitUpdate, current_user: User = Depends(get_current_user)):
    habit = await db.habits.find_one({"id": habit_id, "user_id": current_user.id})
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    
    update_data = {k: v for k, v in habit_data.dict().items() if v is not None}
    if update_data:
        await db.habits.update_one({"id": habit_id}, {"$set": update_data})
        habit.update(update_data)
    
    return Habit(**habit)

@api_router.delete("/habits/{habit_id}")
async def delete_habit(habit_id: str, current_user: User = Depends(get_current_user)):
    result = await db.habits.update_one(
        {"id": habit_id, "user_id": current_user.id}, 
        {"$set": {"is_active": False}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Habit not found")
    return {"message": "Habit deleted successfully"}

# Habit Tracking Routes
@api_router.post("/habits/{habit_id}/track")
async def track_habit(habit_id: str, record_data: HabitRecordCreate, current_user: User = Depends(get_current_user)):
    # Verify habit exists and belongs to user
    habit = await db.habits.find_one({"id": habit_id, "user_id": current_user.id})
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    
    # Check if already tracked for today
    today = date.today()
    existing_record = await db.habit_records.find_one({
        "habit_id": habit_id,
        "user_id": current_user.id,
        "date": today.isoformat()
    })
    
    if existing_record:
        # Update existing record
        update_data = record_data.dict()
        await db.habit_records.update_one(
            {"id": existing_record["id"]}, 
            {"$set": update_data}
        )
        existing_record.update(update_data)
        record = HabitRecord(**existing_record)
    else:
        # Create new record
        record = HabitRecord(
            user_id=current_user.id,
            habit_id=habit_id,
            date=today,
            **record_data.dict()
        )
        # Convert date to string before storing in MongoDB
        record_dict = record.dict()
        record_dict["date"] = record_dict["date"].isoformat()
        await db.habit_records.insert_one(record_dict)
    
    # Send Slack notification if enabled
    if habit.get("slack_notifications") and current_user.slack_user_id and record_data.completed:
        habit_name = habit["name"]
        value_text = ""
        if record_data.value and habit.get("target_value"):
            value_text = f" ({record_data.value}/{habit['target_value']} {habit.get('target_unit', '')})"
        
        message = f"🎉 Great job! {current_user.name} completed: {habit_name}{value_text}"
        
        # Try to send to user's DM
        await send_slack_message(current_user.slack_user_id, message)
    
    return record

@api_router.get("/habits/{habit_id}/records")
async def get_habit_records(habit_id: str, days: int = 30, current_user: User = Depends(get_current_user)):
    # Verify habit exists and belongs to user
    habit = await db.habits.find_one({"id": habit_id, "user_id": current_user.id})
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    
    start_date = date.today() - timedelta(days=days)
    records = await db.habit_records.find({
        "habit_id": habit_id,
        "user_id": current_user.id,
        "date": {"$gte": start_date.isoformat()}
    }).to_list(1000)
    
    # Convert date strings back to date objects for the response
    for record in records:
        if isinstance(record["date"], str):
            try:
                record["date"] = date.fromisoformat(record["date"])
            except ValueError:
                # If date can't be parsed, keep it as string
                pass
    
    return [HabitRecord(**record) for record in records]

# Dashboard and Stats Routes
@api_router.get("/dashboard")
async def get_dashboard(current_user: User = Depends(get_current_user)):
    today = date.today()
    
    # Get all active habits
    habits = await db.habits.find({"user_id": current_user.id, "is_active": True}).to_list(1000)
    
    # Get today's records
    today_records = await db.habit_records.find({
        "user_id": current_user.id,
        "date": today.isoformat()
    }).to_list(1000)
    
    records_by_habit = {record["habit_id"]: record for record in today_records}
    
    # Build dashboard data
    dashboard_habits = []
    for habit in habits:
        habit_data = Habit(**habit)
        record = records_by_habit.get(habit["id"])
        dashboard_habits.append({
            "habit": habit_data,
            "today_record": HabitRecord(**record) if record else None,
            "is_completed_today": record["completed"] if record else False
        })
    
    # Calculate stats
    total_habits = len(habits)
    completed_today = len([r for r in today_records if r["completed"]])
    completion_rate = (completed_today / total_habits * 100) if total_habits > 0 else 0
    
    return {
        "habits": dashboard_habits,
        "stats": {
            "total_habits": total_habits,
            "completed_today": completed_today,
            "completion_rate": round(completion_rate, 1)
        }
    }

@api_router.get("/stats/streaks")
async def get_streaks(current_user: User = Depends(get_current_user)):
    habits = await db.habits.find({"user_id": current_user.id, "is_active": True}).to_list(1000)
    
    streaks = []
    for habit in habits:
        # Get recent records for this habit
        records = await db.habit_records.find({
            "habit_id": habit["id"],
            "user_id": current_user.id,
            "completed": True
        }).sort("date", -1).to_list(365)  # Last year
        
        # Calculate current streak
        current_streak = 0
        current_date = date.today()
        
        for record in records:
            if isinstance(record["date"], str):
                record_date = datetime.fromisoformat(record["date"]).date()
            else:
                record_date = record["date"]
                
            if record_date == current_date:
                current_streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        # Calculate best streak
        best_streak = 0
        temp_streak = 0
        prev_date = None
        
        sorted_records = sorted([r for r in records], key=lambda x: 
            datetime.fromisoformat(x["date"]).date() if isinstance(x["date"], str) else x["date"])
        
        for record in sorted_records:
            record_date = datetime.fromisoformat(record["date"]).date() if isinstance(record["date"], str) else record["date"]
            
            if prev_date is None or record_date == prev_date + timedelta(days=1):
                temp_streak += 1
                best_streak = max(best_streak, temp_streak)
            else:
                temp_streak = 1
            
            prev_date = record_date
        
        streaks.append({
            "habit_id": habit["id"],
            "habit_name": habit["name"],
            "current_streak": current_streak,
            "best_streak": best_streak,
            "total_completions": len(records)
        })
    
    return streaks

# Advanced Analytics Routes
@api_router.get("/analytics/overview")
async def get_analytics_overview(days: int = 30, current_user: User = Depends(get_current_user)):
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Get all habits and records
    habits = await db.habits.find({"user_id": current_user.id, "is_active": True}).to_list(1000)
    records = await db.habit_records.find({
        "user_id": current_user.id,
        "date": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}
    }).to_list(10000)
    
    # Process data for analytics
    daily_completions = defaultdict(int)
    daily_totals = defaultdict(int)
    category_stats = defaultdict(lambda: {"completed": 0, "total": 0})
    habit_performance = {}
    
    habits_by_id = {h["id"]: h for h in habits}
    
    # Generate daily data
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.isoformat()
        daily_totals[date_str] = len(habits)
        current_date += timedelta(days=1)
    
    # Process records
    for record in records:
        record_date = record["date"] if isinstance(record["date"], str) else record["date"].isoformat()
        habit_id = record["habit_id"]
        
        if record["completed"]:
            daily_completions[record_date] += 1
            
            habit = habits_by_id.get(habit_id)
            if habit and habit.get("category"):
                category_stats[habit["category"]]["completed"] += 1
        
        # Track habit performance
        if habit_id not in habit_performance:
            habit_performance[habit_id] = {"completed": 0, "total": 0, "name": habits_by_id.get(habit_id, {}).get("name", "Unknown")}
        
        habit_performance[habit_id]["total"] += 1
        if record["completed"]:
            habit_performance[habit_id]["completed"] += 1
    
    # Add category totals
    for habit in habits:
        if habit.get("category"):
            category_stats[habit["category"]]["total"] += days
    
    # Prepare chart data
    chart_data = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.isoformat()
        completion_rate = (daily_completions[date_str] / daily_totals[date_str] * 100) if daily_totals[date_str] > 0 else 0
        chart_data.append({
            "date": date_str,
            "completed": daily_completions[date_str],
            "total": daily_totals[date_str],
            "completion_rate": round(completion_rate, 1)
        })
        current_date += timedelta(days=1)
    
    # Calculate habit success rates
    habit_stats = []
    for habit_id, stats in habit_performance.items():
        success_rate = (stats["completed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        habit_stats.append({
            "habit_id": habit_id,
            "name": stats["name"],
            "success_rate": round(success_rate, 1),
            "completed": stats["completed"],
            "total": stats["total"]
        })
    
    return {
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "chart_data": chart_data,
        "category_stats": dict(category_stats),
        "habit_stats": sorted(habit_stats, key=lambda x: x["success_rate"], reverse=True),
        "summary": {
            "total_habits": len(habits),
            "total_completions": sum(daily_completions.values()),
            "average_completion_rate": round(sum(r["completion_rate"] for r in chart_data) / len(chart_data), 1) if chart_data else 0
        }
    }

# Export/Import Routes
@api_router.get("/export/habits")
async def export_habits(format: str = "json", current_user: User = Depends(get_current_user)):
    # Get user's habits and records
    habits = await db.habits.find({"user_id": current_user.id}).to_list(1000)
    records = await db.habit_records.find({"user_id": current_user.id}).to_list(10000)
    
    # Clean data for export
    export_habits = []
    for habit in habits:
        habit_data = dict(habit)
        habit_data.pop("user_id", None)
        habit_data["created_at"] = habit_data["created_at"].isoformat() if isinstance(habit_data.get("created_at"), datetime) else habit_data.get("created_at")
        export_habits.append(habit_data)
    
    export_records = []
    for record in records:
        record_data = dict(record)
        record_data.pop("user_id", None)
        record_data["date"] = record_data["date"] if isinstance(record_data["date"], str) else record_data["date"].isoformat()
        record_data["created_at"] = record_data["created_at"].isoformat() if isinstance(record_data.get("created_at"), datetime) else record_data.get("created_at")
        export_records.append(record_data)
    
    export_data = {
        "habits": export_habits,
        "records": export_records,
        "exported_at": datetime.utcnow().isoformat(),
        "user_name": current_user.name
    }
    
    if format.lower() == "csv":
        # Create CSV files in memory
        habits_csv = io.StringIO()
        records_csv = io.StringIO()
        
        if export_habits:
            habits_writer = csv.DictWriter(habits_csv, fieldnames=export_habits[0].keys())
            habits_writer.writeheader()
            habits_writer.writerows(export_habits)
        
        if export_records:
            records_writer = csv.DictWriter(records_csv, fieldnames=export_records[0].keys())
            records_writer.writeheader()
            records_writer.writerows(export_records)
        
        # Create a combined CSV response
        combined_csv = io.StringIO()
        combined_csv.write("# HABITS DATA\n")
        combined_csv.write(habits_csv.getvalue())
        combined_csv.write("\n\n# RECORDS DATA\n")
        combined_csv.write(records_csv.getvalue())
        
        response = StreamingResponse(
            io.BytesIO(combined_csv.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=habits_export_{date.today().isoformat()}.csv"}
        )
        return response
    
    else:  # JSON format
        response = StreamingResponse(
            io.BytesIO(json.dumps(export_data, indent=2).encode()),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=habits_export_{date.today().isoformat()}.json"}
        )
        return response

@api_router.post("/import/habits")
async def import_habits(import_data: ImportData, current_user: User = Depends(get_current_user)):
    imported_habits = 0
    imported_records = 0
    errors = []
    
    # Import habits
    for habit_data in import_data.habits:
        try:
            # Clean and prepare habit data
            habit_data["user_id"] = current_user.id
            habit_data["id"] = str(uuid.uuid4())  # Generate new ID
            habit_data["created_at"] = datetime.utcnow()
            
            # Validate required fields
            if not habit_data.get("name") or not habit_data.get("habit_type"):
                errors.append(f"Skipped habit: missing required fields")
                continue
            
            habit = Habit(**habit_data)
            await db.habits.insert_one(habit.dict())
            imported_habits += 1
            
        except Exception as e:
            errors.append(f"Error importing habit: {str(e)}")
    
    # Import records if provided
    if import_data.records:
        # Get habit ID mapping (old -> new)
        habit_mapping = {}
        imported_habit_names = [h.get("name") for h in import_data.habits]
        existing_habits = await db.habits.find({
            "user_id": current_user.id,
            "name": {"$in": imported_habit_names}
        }).to_list(1000)
        
        for habit in existing_habits:
            # Map by name (assuming names are unique per user)
            habit_mapping[habit["name"]] = habit["id"]
        
        for record_data in import_data.records:
            try:
                # Find the habit ID for this record
                habit_id_found = False
                for habit in import_data.habits:
                    if habit.get("id") == record_data.get("habit_id"):
                        habit_name = habit.get("name")
                        if habit_name in habit_mapping:
                            record_data["habit_id"] = habit_mapping[habit_name]
                            habit_id_found = True
                            break
                
                if not habit_id_found:
                    errors.append(f"Skipped record: habit not found")
                    continue
                
                record_data["user_id"] = current_user.id
                record_data["id"] = str(uuid.uuid4())
                record_data["created_at"] = datetime.utcnow()
                
                # Ensure date is in correct format
                if isinstance(record_data.get("date"), str):
                    try:
                        datetime.fromisoformat(record_data["date"])
                    except ValueError:
                        errors.append(f"Skipped record: invalid date format")
                        continue
                
                await db.habit_records.insert_one(record_data)
                imported_records += 1
                
            except Exception as e:
                errors.append(f"Error importing record: {str(e)}")
    
    return {
        "success": True,
        "imported_habits": imported_habits,
        "imported_records": imported_records,
        "errors": errors
    }

# Notification Routes
@api_router.get("/notifications/reminders")
async def get_reminders(current_user: User = Depends(get_current_user)):
    """Get habits that have reminders enabled"""
    habits = await db.habits.find({
        "user_id": current_user.id,
        "is_active": True,
        "reminder_enabled": True
    }).to_list(1000)
    
    # Check which habits haven't been completed today
    today = date.today()
    today_records = await db.habit_records.find({
        "user_id": current_user.id,
        "date": today.isoformat(),
        "completed": True
    }).to_list(1000)
    
    completed_habit_ids = {record["habit_id"] for record in today_records}
    
    pending_reminders = []
    for habit in habits:
        if habit["id"] not in completed_habit_ids:
            pending_reminders.append({
                "habit_id": habit["id"],
                "name": habit["name"],
                "reminder_time": habit.get("reminder_time"),
                "category": habit.get("category"),
                "color": habit.get("color")
            })
    
    return pending_reminders

# Social Sharing Routes
@api_router.get("/share/progress")
async def get_share_data(current_user: User = Depends(get_current_user)):
    """Generate shareable progress data"""
    # Get recent stats
    analytics = await get_analytics_overview(days=7, current_user=current_user)
    streaks = await get_streaks(current_user=current_user)
    
    # Find best achievements
    best_streak = max(streaks, key=lambda x: x["current_streak"]) if streaks else None
    top_habit = max(analytics["habit_stats"], key=lambda x: x["success_rate"]) if analytics["habit_stats"] else None
    
    share_data = {
        "user_name": current_user.name,
        "period": "7 days",
        "completion_rate": analytics["summary"]["average_completion_rate"],
        "total_habits": analytics["summary"]["total_habits"],
        "total_completions": analytics["summary"]["total_completions"],
        "best_streak": {
            "habit_name": best_streak["habit_name"],
            "streak_count": best_streak["current_streak"]
        } if best_streak else None,
        "top_performing_habit": {
            "name": top_habit["name"],
            "success_rate": top_habit["success_rate"]
        } if top_habit else None,
        "share_text": f"🎯 {current_user.name}'s Habit Progress: {analytics['summary']['average_completion_rate']}% completion rate with {analytics['summary']['total_completions']} habits completed this week! #HabitTracker #Progress"
    }
    
    return share_data

@api_router.post("/share/slack")
async def share_to_slack(channel: str, current_user: User = Depends(get_current_user)):
    """Share progress to Slack channel"""
    try:
        share_data = await get_share_data(current_user=current_user)
        
        # Create rich Slack message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🎯 {share_data['user_name']}'s Habit Progress"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Completion Rate:*\n{share_data['completion_rate']}%"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Completed This Week:*\n{share_data['total_completions']} habits"
                    }
                ]
            }
        ]
        
        if share_data["best_streak"]:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🔥 *Current Streak:* {share_data['best_streak']['streak_count']} days on '{share_data['best_streak']['habit_name']}'"
                }
            })
        
        if share_data["top_performing_habit"]:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⭐ *Top Habit:* '{share_data['top_performing_habit']['name']}' at {share_data['top_performing_habit']['success_rate']}% success rate"
                }
            })
        
        result = await send_slack_message(channel, share_data["share_text"], blocks)
        
        if result.get("ok"):
            return {"success": True, "message": "Progress shared to Slack successfully!"}
        else:
            return {"success": False, "error": result.get("error", "Failed to send message")}
            
    except Exception as e:
        logger.error(f"Failed to share to Slack: {e}")
        return {"success": False, "error": str(e)}

# Slack Integration Routes
@api_router.post("/slack/events")
async def slack_events(request: Request):
    """Handle Slack events (webhooks)"""
    try:
        # Get request data
        body = await request.body()
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        
        # Verify the request is from Slack
        if not verify_slack_signature(timestamp, body, signature):
            raise HTTPException(status_code=401, detail="Invalid Slack signature")
        
        # Parse the JSON data
        data = json.loads(body.decode())
        
        # Handle URL verification challenge
        if data.get("type") == "url_verification":
            return {"challenge": data.get("challenge")}
        
        # Handle events
        if data.get("type") == "event_callback":
            event = data.get("event", {})
            
            # Handle app mentions for habit tracking
            if event.get("type") == "app_mention":
                user_id = event.get("user")
                channel = event.get("channel")
                text = event.get("text", "").lower()
                
                # Find user by Slack ID
                user = await db.users.find_one({"slack_user_id": user_id})
                if not user:
                    await send_slack_message(channel, "Hi! Please connect your habit tracker account first by logging into the app and linking your Slack account.")
                    return {"ok": True}
                
                # Handle different commands
                if "status" in text or "progress" in text:
                    # Show current progress
                    dashboard_data = await get_dashboard(User(**user))
                    stats = dashboard_data["stats"]
                    
                    message = f"📊 Your habit progress today:\n"
                    message += f"• {stats['completed_today']}/{stats['total_habits']} habits completed\n"
                    message += f"• {stats['completion_rate']}% completion rate"
                    
                    await send_slack_message(channel, message)
                
                elif "habits" in text or "list" in text:
                    # List active habits
                    habits = await db.habits.find({"user_id": user["id"], "is_active": True}).to_list(10)
                    
                    if habits:
                        message = "📝 Your active habits:\n"
                        for i, habit in enumerate(habits[:5], 1):
                            message += f"{i}. {habit['name']}\n"
                        if len(habits) > 5:
                            message += f"... and {len(habits) - 5} more"
                    else:
                        message = "You don't have any active habits yet. Create some in your habit tracker!"
                    
                    await send_slack_message(channel, message)
                
                else:
                    # Default help message
                    help_text = """👋 Hi! I can help you with your habits. Try:
• `@habitbot status` - See your progress
• `@habitbot habits` - List your habits
• `@habitbot help` - Show this message

Visit your habit tracker app to manage your habits and connect your Slack account!"""
                    
                    await send_slack_message(channel, help_text)
        
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"Slack events error: {e}")
        return {"ok": False, "error": str(e)}

@api_router.get("/slack/install")
async def slack_install_info():
    """Provide Slack app installation information"""
    backend_url = os.environ.get('REACT_APP_BACKEND_URL', 'YOUR_BACKEND_URL')
    
    return {
        "webhook_url": f"{backend_url}/api/slack/events",
        "setup_instructions": [
            "1. Go to https://api.slack.com/apps and create a new app",
            "2. Choose 'From scratch' and name your app 'Habit Tracker Bot'",
            "3. In 'OAuth & Permissions', add these Bot Token Scopes:",
            "   - app_mentions:read",
            "   - channels:read", 
            "   - chat:write",
            "   - users:read",
            "4. In 'Event Subscriptions', enable events and add this URL:",
            f"   {backend_url}/api/slack/events",
            "5. Subscribe to these bot events:",
            "   - app_mention",
            "6. Install the app to your workspace",
            "7. Copy the Bot User OAuth Token and add it to your .env file as SLACK_BOT_TOKEN",
            "8. Copy the Signing Secret and add it to your .env file as SLACK_SIGNING_SECRET",
            "9. Restart your backend server",
            "10. Mention @habitbot in any channel to start using it!"
        ],
        "required_env_vars": {
            "SLACK_BOT_TOKEN": "Bot User OAuth Token (starts with xoxb-)",
            "SLACK_SIGNING_SECRET": "Signing Secret from Basic Information page"
        }
    }

@api_router.get("/slack/status")
async def slack_status():
    """Check Slack integration status"""
    return {
        "configured": bool(SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET),
        "bot_token_present": bool(SLACK_BOT_TOKEN),
        "signing_secret_present": bool(SLACK_SIGNING_SECRET),
        "webhook_url": f"{os.environ.get('REACT_APP_BACKEND_URL', 'YOUR_BACKEND_URL')}/api/slack/events"
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()