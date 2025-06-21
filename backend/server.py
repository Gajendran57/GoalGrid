from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
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

class HabitUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None

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
        return HabitRecord(**existing_record)
    else:
        # Create new record
        record = HabitRecord(
            user_id=current_user.id,
            habit_id=habit_id,
            date=today,
            **record_data.dict()
        )
        await db.habit_records.insert_one(record.dict())
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
            record_date = datetime.fromisoformat(record["date"]).date()
            if record_date == current_date:
                current_streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        streaks.append({
            "habit_id": habit["id"],
            "habit_name": habit["name"],
            "current_streak": current_streak,
            "total_completions": len(records)
        })
    
    return streaks

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