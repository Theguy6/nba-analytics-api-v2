"""
Database models for NBA Analytics
PostgreSQL schema for storing game stats and pre-calculated metrics
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Player(Base):
    """NBA Player information"""
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True)  # Balldontlie player ID
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    position = Column(String(10))
    team_id = Column(Integer)
    team_name = Column(String(100))
    team_abbreviation = Column(String(10))
    
    # Relationships
    game_stats = relationship("GameStats", back_populates="player")
    
    __table_args__ = (
        Index('idx_player_name', 'first_name', 'last_name'),
    )
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class Team(Base):
    """NBA Team information"""
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True)  # Balldontlie team ID
    abbreviation = Column(String(10), nullable=False, unique=True)
    city = Column(String(100))
    conference = Column(String(10))
    division = Column(String(20))
    full_name = Column(String(100))
    name = Column(String(100))
    
    # Relationships
    home_games = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    visitor_games = relationship("Game", foreign_keys="Game.visitor_team_id", back_populates="visitor_team")

class Game(Base):
    """NBA Game information"""
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True)  # Balldontlie game ID
    date = Column(Date, nullable=False)
    season = Column(Integer, nullable=False)
    status = Column(String(50))
    
    # Teams
    home_team_id = Column(Integer, ForeignKey('teams.id'))
    visitor_team_id = Column(Integer, ForeignKey('teams.id'))
    
    # Scores
    home_team_score = Column(Integer)
    visitor_team_score = Column(Integer)
    
    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    visitor_team = relationship("Team", foreign_keys=[visitor_team_id], back_populates="visitor_games")
    game_stats = relationship("GameStats", back_populates="game")
    
    __table_args__ = (
        Index('idx_game_date', 'date'),
        Index('idx_game_season', 'season'),
        Index('idx_game_teams', 'home_team_id', 'visitor_team_id'),
    )

class GameStats(Base):
    """Player statistics for a specific game"""
    __tablename__ = "game_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign keys
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False)
    team_id = Column(Integer, ForeignKey('teams.id'))
    
    # Game context
    is_home = Column(Boolean)
    minutes = Column(String(10))  # "35:42" format
    
    # Shooting stats
    fgm = Column(Integer, default=0)  # Field Goals Made
    fga = Column(Integer, default=0)  # Field Goals Attempted
    fg_pct = Column(Float)
    fg3m = Column(Integer, default=0)  # Three Pointers Made
    fg3a = Column(Integer, default=0)  # Three Pointers Attempted
    fg3_pct = Column(Float)
    ftm = Column(Integer, default=0)  # Free Throws Made
    fta = Column(Integer, default=0)  # Free Throws Attempted
    ft_pct = Column(Float)
    
    # Other stats
    oreb = Column(Integer, default=0)  # Offensive Rebounds
    dreb = Column(Integer, default=0)  # Defensive Rebounds
    reb = Column(Integer, default=0)   # Total Rebounds
    ast = Column(Integer, default=0)   # Assists
    stl = Column(Integer, default=0)   # Steals
    blk = Column(Integer, default=0)   # Blocks
    turnover = Column(Integer, default=0)
    pf = Column(Integer, default=0)    # Personal Fouls
    pts = Column(Integer, default=0)   # Points
    
    # Advanced stats (can be calculated)
    plus_minus = Column(Integer)
    
    # Relationships
    player = relationship("Player", back_populates="game_stats")
    game = relationship("Game", back_populates="game_stats")
    
    __table_args__ = (
        Index('idx_stats_player', 'player_id'),
        Index('idx_stats_game', 'game_id'),
        Index('idx_stats_player_game', 'player_id', 'game_id'),
    )

class MetricCache(Base):
    """Pre-calculated metrics for fast queries"""
    __tablename__ = "metric_cache"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Metric identification
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    metric_type = Column(String(50), nullable=False)  # "three_point_rate", "assists_rate", etc.
    season = Column(Integer, nullable=False)
    
    # Metric parameters
    threshold = Column(Integer)  # e.g., 3 for "3+ threes"
    window_size = Column(Integer)  # e.g., 10 games
    
    # Results (stored as JSON-compatible text or separate columns)
    overall_rate = Column(Float)
    home_rate = Column(Float)
    away_rate = Column(Float)
    games_analyzed = Column(Integer)
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_cache_player_metric', 'player_id', 'metric_type', 'season'),
    )

class SyncLog(Base):
    """Track data synchronization"""
    __tablename__ = "sync_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_date = Column(DateTime, default=datetime.utcnow)
    season = Column(Integer)
    games_synced = Column(Integer)
    status = Column(String(20))  # "success", "partial", "failed"
    error_message = Column(String(500))
    
    __table_args__ = (
        Index('idx_sync_date', 'sync_date'),
    )
