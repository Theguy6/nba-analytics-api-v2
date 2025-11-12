"""
Enhanced Database models for GOAT tier features
Adds: Season Averages, Advanced Stats, Team Standings, Leaders, Injuries
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Index, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base

# Add these new tables to your existing database.py

class SeasonAverages(Base):
    """Player season averages (GOAT tier)"""
    __tablename__ = "season_averages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Game stats
    games_played = Column(Integer)
    
    # Averages
    minutes = Column(Float)
    fgm = Column(Float)
    fga = Column(Float)
    fg_pct = Column(Float)
    fg3m = Column(Float)
    fg3a = Column(Float)
    fg3_pct = Column(Float)
    ftm = Column(Float)
    fta = Column(Float)
    ft_pct = Column(Float)
    oreb = Column(Float)
    dreb = Column(Float)
    reb = Column(Float)
    ast = Column(Float)
    stl = Column(Float)
    blk = Column(Float)
    turnover = Column(Float)
    pf = Column(Float)
    pts = Column(Float)
    
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_season_avg_player_season', 'player_id', 'season'),
    )


class AdvancedStats(Base):
    """Advanced game statistics (GOAT tier)"""
    __tablename__ = "advanced_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_stats_id = Column(Integer, ForeignKey('game_stats.id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False)
    
    # Advanced metrics
    true_shooting_pct = Column(Float)
    effective_fg_pct = Column(Float)
    usage_rate = Column(Float)
    pace = Column(Float)
    pie = Column(Float)  # Player Impact Estimate
    
    __table_args__ = (
        Index('idx_adv_stats_player_game', 'player_id', 'game_id'),
    )


class TeamStandings(Base):
    """Team standings by season (GOAT tier)"""
    __tablename__ = "team_standings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Record
    wins = Column(Integer)
    losses = Column(Integer)
    win_pct = Column(Float)
    games_back = Column(Float)
    
    # Standings
    conference_rank = Column(Integer)
    division_rank = Column(Integer)
    
    # Home/Away
    home_wins = Column(Integer)
    home_losses = Column(Integer)
    away_wins = Column(Integer)
    away_losses = Column(Integer)
    
    # Streaks
    last_10 = Column(String(20))  # "7-3"
    streak = Column(String(10))  # "W3" or "L2"
    
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_standings_team_season', 'team_id', 'season'),
    )


class LeagueLeaders(Base):
    """League leaders in various categories (GOAT tier)"""
    __tablename__ = "league_leaders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    season = Column(Integer, nullable=False)
    category = Column(String(50), nullable=False)  # "points", "assists", "rebounds", etc.
    
    value = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False)
    
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_leaders_season_category', 'season', 'category'),
        Index('idx_leaders_player', 'player_id', 'season'),
    )


class PlayerInjury(Base):
    """Player injury reports (GOAT tier)"""
    __tablename__ = "player_injuries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    
    injury_type = Column(String(100))  # "ankle sprain", "knee injury", etc.
    status = Column(String(50))  # "out", "day-to-day", "questionable", "probable"
    description = Column(Text)
    
    date_reported = Column(Date)
    date_updated = Column(Date)
    expected_return = Column(Date)
    
    __table_args__ = (
        Index('idx_injuries_player', 'player_id'),
        Index('idx_injuries_status', 'status'),
    )


class BoxScore(Base):
    """Complete game box scores (GOAT tier)"""
    __tablename__ = "box_scores"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False, unique=True)
    
    # Score by quarter
    home_q1 = Column(Integer)
    home_q2 = Column(Integer)
    home_q3 = Column(Integer)
    home_q4 = Column(Integer)
    home_ot = Column(Integer)
    
    away_q1 = Column(Integer)
    away_q2 = Column(Integer)
    away_q3 = Column(Integer)
    away_q4 = Column(Integer)
    away_ot = Column(Integer)
    
    # Additional info
    attendance = Column(Integer)
    duration = Column(String(20))  # "2:15"
    
    __table_args__ = (
        Index('idx_boxscore_game', 'game_id'),
    )
