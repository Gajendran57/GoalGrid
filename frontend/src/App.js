import React, { useState, useEffect, createContext, useContext } from 'react';
import './App.css';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Auth Context
const AuthContext = createContext();

const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUser();
    } else {
      setLoading(false);
    }
  }, []);

  const fetchUser = async () => {
    try {
      const response = await axios.get(`${API}/auth/me`);
      setUser(response.data);
    } catch (error) {
      localStorage.removeItem('token');
      delete axios.defaults.headers.common['Authorization'];
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const response = await axios.post(`${API}/auth/login`, { email, password });
    const { access_token, user } = response.data;
    localStorage.setItem('token', access_token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setUser(user);
    return user;
  };

  const register = async (name, email, password) => {
    const response = await axios.post(`${API}/auth/register`, { name, email, password });
    const { access_token, user } = response.data;
    localStorage.setItem('token', access_token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setUser(user);
    return user;
  };

  const logout = () => {
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

// Components
const LoginForm = ({ onSwitchToRegister }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      await login(email, password);
    } catch (error) {
      setError(error.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2 className="auth-title">Welcome Back</h2>
        <p className="auth-subtitle">Sign in to your habit tracker</p>
        
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label className="form-label">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="form-input"
              required
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="form-input"
              required
            />
          </div>
          
          {error && <div className="error-message">{error}</div>}
          
          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
        
        <p className="auth-switch">
          Don't have an account?{' '}
          <button onClick={onSwitchToRegister} className="link-button">
            Sign up
          </button>
        </p>
      </div>
    </div>
  );
};

const RegisterForm = ({ onSwitchToLogin }) => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      await register(name, email, password);
    } catch (error) {
      setError(error.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2 className="auth-title">Create Account</h2>
        <p className="auth-subtitle">Start tracking your habits today</p>
        
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label className="form-label">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="form-input"
              required
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="form-input"
              required
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="form-input"
              required
            />
          </div>
          
          {error && <div className="error-message">{error}</div>}
          
          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>
        
        <p className="auth-switch">
          Already have an account?{' '}
          <button onClick={onSwitchToLogin} className="link-button">
            Sign in
          </button>
        </p>
      </div>
    </div>
  );
};

const HabitForm = ({ habit, onSave, onCancel }) => {
  const [formData, setFormData] = useState({
    name: habit?.name || '',
    description: habit?.description || '',
    habit_type: habit?.habit_type || 'yes_no',
    target_value: habit?.target_value || '',
    target_unit: habit?.target_unit || '',
    category: habit?.category || '',
    color: habit?.color || '#8B5CF6'
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    const data = { ...formData };
    if (data.target_value) data.target_value = parseFloat(data.target_value);
    onSave(data);
  };

  const habitTypes = [
    { value: 'yes_no', label: 'Yes/No (Did it or didn\'t)' },
    { value: 'quantifiable', label: 'Quantifiable (Track numbers)' },
    { value: 'time_based', label: 'Time-based (Track duration)' }
  ];

  const colors = [
    '#8B5CF6', '#EF4444', '#F59E0B', '#10B981', '#3B82F6', '#8B5A2B', '#EC4899'
  ];

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h3 className="modal-title">
          {habit ? 'Edit Habit' : 'Create New Habit'}
        </h3>
        
        <form onSubmit={handleSubmit} className="habit-form">
          <div className="form-group">
            <label className="form-label">Habit Name *</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({...formData, name: e.target.value})}
              className="form-input"
              required
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({...formData, description: e.target.value})}
              className="form-textarea"
              rows="3"
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Habit Type *</label>
            <select
              value={formData.habit_type}
              onChange={(e) => setFormData({...formData, habit_type: e.target.value})}
              className="form-select"
              required
            >
              {habitTypes.map(type => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>
          
          {formData.habit_type !== 'yes_no' && (
            <>
              <div className="form-group">
                <label className="form-label">Target Value</label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.target_value}
                  onChange={(e) => setFormData({...formData, target_value: e.target.value})}
                  className="form-input"
                />
              </div>
              
              <div className="form-group">
                <label className="form-label">Unit</label>
                <input
                  type="text"
                  value={formData.target_unit}
                  onChange={(e) => setFormData({...formData, target_unit: e.target.value})}
                  className="form-input"
                  placeholder="e.g., minutes, glasses, pages"
                />
              </div>
            </>
          )}
          
          <div className="form-group">
            <label className="form-label">Category</label>
            <input
              type="text"
              value={formData.category}
              onChange={(e) => setFormData({...formData, category: e.target.value})}
              className="form-input"
              placeholder="e.g., Health, Learning, Productivity"
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Color</label>
            <div className="color-picker">
              {colors.map(color => (
                <button
                  key={color}
                  type="button"
                  className={`color-option ${formData.color === color ? 'selected' : ''}`}
                  style={{ backgroundColor: color }}
                  onClick={() => setFormData({...formData, color})}
                />
              ))}
            </div>
          </div>
          
          <div className="form-actions">
            <button type="button" onClick={onCancel} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" className="btn-primary">
              {habit ? 'Update Habit' : 'Create Habit'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const HabitCard = ({ habitData, onEdit, onDelete, onTrack }) => {
  const { habit, today_record, is_completed_today } = habitData;
  
  const handleTrack = () => {
    if (habit.habit_type === 'yes_no') {
      onTrack(habit.id, { completed: !is_completed_today });
    } else {
      // For quantifiable/time_based habits, show input
      const value = prompt(`Enter ${habit.target_unit || 'value'}:`);
      if (value !== null) {
        onTrack(habit.id, { 
          completed: true, 
          value: parseFloat(value) || 0 
        });
      }
    }
  };

  return (
    <div className="habit-card" style={{ borderLeft: `4px solid ${habit.color}` }}>
      <div className="habit-header">
        <div className="habit-info">
          <h3 className="habit-name">{habit.name}</h3>
          {habit.description && (
            <p className="habit-description">{habit.description}</p>
          )}
          {habit.category && (
            <span className="habit-category">{habit.category}</span>
          )}
        </div>
        
        <div className="habit-actions">
          <button onClick={() => onEdit(habit)} className="btn-icon" title="Edit">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button onClick={() => onDelete(habit.id)} className="btn-icon text-red-500" title="Delete">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
      
      <div className="habit-progress">
        {habit.habit_type === 'yes_no' ? (
          <button
            onClick={handleTrack}
            className={`habit-check ${is_completed_today ? 'completed' : ''}`}
          >
            {is_completed_today ? '✓' : '○'}
          </button>
        ) : (
          <div className="habit-value">
            <div className="current-value">
              {today_record?.value || 0} / {habit.target_value || 0} {habit.target_unit}
            </div>
            <button onClick={handleTrack} className="btn-track">
              Track
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

const Dashboard = () => {
  const { user, logout } = useAuth();
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showHabitForm, setShowHabitForm] = useState(false);
  const [editingHabit, setEditingHabit] = useState(null);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await axios.get(`${API}/dashboard`);
      setDashboardData(response.data);
    } catch (error) {
      console.error('Failed to fetch dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateHabit = () => {
    setEditingHabit(null);
    setShowHabitForm(true);
  };

  const handleEditHabit = (habit) => {
    setEditingHabit(habit);
    setShowHabitForm(true);
  };

  const handleSaveHabit = async (habitData) => {
    try {
      if (editingHabit) {
        await axios.put(`${API}/habits/${editingHabit.id}`, habitData);
      } else {
        await axios.post(`${API}/habits`, habitData);
      }
      setShowHabitForm(false);
      setEditingHabit(null);
      fetchDashboard();
    } catch (error) {
      console.error('Failed to save habit:', error);
    }
  };

  const handleDeleteHabit = async (habitId) => {
    if (window.confirm('Are you sure you want to delete this habit?')) {
      try {
        await axios.delete(`${API}/habits/${habitId}`);
        fetchDashboard();
      } catch (error) {
        console.error('Failed to delete habit:', error);
      }
    }
  };

  const handleTrackHabit = async (habitId, recordData) => {
    try {
      await axios.post(`${API}/habits/${habitId}/track`, recordData);
      fetchDashboard();
    } catch (error) {
      console.error('Failed to track habit:', error);
    }
  };

  if (loading) {
    return <div className="loading">Loading your habits...</div>;
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="header-content">
          <div>
            <h1 className="dashboard-title">Good morning, {user.name}!</h1>
            <p className="dashboard-subtitle">Let's build great habits together</p>
          </div>
          <div className="header-actions">
            <button onClick={handleCreateHabit} className="btn-primary">
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Habit
            </button>
            <button onClick={logout} className="btn-secondary">
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {dashboardData && (
        <>
          <div className="stats-grid">
            <div className="stats-card stats-card-total">
              <h3 className="stats-title">Total Habits</h3>
              <p className="stats-value">{dashboardData.stats.total_habits}</p>
            </div>
            <div className="stats-card stats-card-completed">
              <h3 className="stats-title">Completed Today</h3>
              <p className="stats-value">{dashboardData.stats.completed_today}</p>
            </div>
            <div className="stats-card stats-card-rate">
              <h3 className="stats-title">Completion Rate</h3>
              <p className="stats-value">{dashboardData.stats.completion_rate}%</p>
            </div>
          </div>

          <div className="habits-section">
            <h2 className="section-title">Today's Habits</h2>
            {dashboardData.habits.length === 0 ? (
              <div className="empty-state">
                <p>No habits yet. Create your first habit to get started!</p>
                <button onClick={handleCreateHabit} className="btn-primary">
                  Create First Habit
                </button>
              </div>
            ) : (
              <div className="habits-grid">
                {dashboardData.habits.map((habitData) => (
                  <HabitCard
                    key={habitData.habit.id}
                    habitData={habitData}
                    onEdit={handleEditHabit}
                    onDelete={handleDeleteHabit}
                    onTrack={handleTrackHabit}
                  />
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {showHabitForm && (
        <HabitForm
          habit={editingHabit}
          onSave={handleSaveHabit}
          onCancel={() => {
            setShowHabitForm(false);
            setEditingHabit(null);
          }}
        />
      )}
    </div>
  );
};

const AuthScreen = () => {
  const [isLogin, setIsLogin] = useState(true);
  
  return isLogin ? (
    <LoginForm onSwitchToRegister={() => setIsLogin(false)} />
  ) : (
    <RegisterForm onSwitchToLogin={() => setIsLogin(true)} />
  );
};

function App() {
  return (
    <AuthProvider>
      <div className="App">
        <AuthenticatedApp />
      </div>
    </AuthProvider>
  );
}

const AuthenticatedApp = () => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return <div className="loading">Loading...</div>;
  }
  
  return user ? <Dashboard /> : <AuthScreen />;
};

export default App;