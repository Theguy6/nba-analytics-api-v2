"""
Database models for NBA Analytics - COMPLETE VERSION
PostgreSQL schema with GOAT tier features
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Index, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

# ============================================================================
# CORE MODELS
# ============================================================================

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
    season_averages = relationship("SeasonAverages", back_populates="player")
    
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
    team_standings = relationship("TeamStandings", back_populates="team")

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


# ============================================================================
# GOAT TIER MODELS
# ============================================================================

class SeasonAverages(Base):
    """Pre-calculated season averages for each player"""
    __tablename__ = "season_averages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign keys
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Basic info
    games_played = Column(Integer)
    
    # Shooting averages
    avg_fgm = Column(Float)
    avg_fga = Column(Float)
    avg_fg_pct = Column(Float)
    avg_fg3m = Column(Float)
    avg_fg3a = Column(Float)
    avg_fg3_pct = Column(Float)
    avg_ftm = Column(Float)
    avg_fta = Column(Float)
    avg_ft_pct = Column(Float)
    
    # Other averages
    avg_oreb = Column(Float)
    avg_dreb = Column(Float)
    avg_reb = Column(Float)
    avg_ast = Column(Float)
    avg_stl = Column(Float)
    avg_blk = Column(Float)
    avg_turnover = Column(Float)
    avg_pf = Column(Float)
    avg_pts = Column(Float)
    avg_minutes = Column(Float)
    
    # Efficiency metrics
    usage_rate = Column(Float)
    true_shooting_pct = Column(Float)
    effective_fg_pct = Column(Float)
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    player = relationship("Player", back_populates="season_averages")
    
    __table_args__ = (
        Index('idx_season_avgs_player', 'player_id', 'season'),
    )


class TeamStandings(Base):
    """NBA Team Standings and Records"""
    __tablename__ = "team_standings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Records
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    win_pct = Column(Float)
    
    # Home/Away splits
    home_wins = Column(Integer, default=0)
    home_losses = Column(Integer, default=0)
    away_wins = Column(Integer, default=0)
    away_losses = Column(Integer, default=0)
    
    # Conference/Division standing
    conference_rank = Column(Integer)
    division_rank = Column(Integer)
    
    # Streaks
    current_streak = Column(String(10))  # "W5", "L2"
    
    # Scoring
    avg_points_scored = Column(Float)
    avg_points_allowed = Column(Float)
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    team = relationship("Team", back_populates="team_standings")
    
    __table_args__ = (
        Index('idx_standings_team_season', 'team_id', 'season'),
    )


class HeadToHead(Base):
    """Head-to-head matchup records between two teams"""
    __tablename__ = "head_to_head"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign keys
    team_1_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    team_2_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Records
    team_1_wins = Column(Integer, default=0)
    team_2_wins = Column(Integer, default=0)
    
    # Scoring
    team_1_avg_score = Column(Float)
    team_2_avg_score = Column(Float)
    
    # Last game info
    last_game_date = Column(Date)
    last_game_winner = Column(Integer, ForeignKey('teams.id'))
    last_game_score = Column(String(20))  # "120-115"
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_h2h_teams', 'team_1_id', 'team_2_id', 'season'),
    )


class InjuryReport(Base):
    """Player injury reports"""
    __tablename__ = "injury_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    
    # Injury info
    injury_status = Column(String(50))  # "Out", "Questionable", "Day-to-Day"
    injury_description = Column(String(200))
    expected_return = Column(Date)
    
    # Metadata
    report_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_injury_player', 'player_id'),
        Index('idx_injury_active', 'is_active'),
    )


class PlayerComparison(Base):
    """Pre-calculated player comparisons for common queries"""
    __tablename__ = "player_comparisons"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign keys
    player_1_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    player_2_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Comparison metrics (JSON stored as text)
    comparison_data = Column(Text)  # JSON with detailed comparison
    
    # Summary
    better_at_scoring = Column(Integer, ForeignKey('players.id'))
    better_at_assists = Column(Integer, ForeignKey('players.id'))
    better_at_rebounds = Column(Integer, ForeignKey('players.id'))
    better_efficiency = Column(Integer, ForeignKey('players.id'))
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_comparison_players', 'player_1_id', 'player_2_id', 'season'),
    )


class GamePrediction(Base):
    """ML-based game predictions"""
    __tablename__ = "game_predictions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False)
    
    # Predictions
    predicted_winner = Column(Integer, ForeignKey('teams.id'))
    confidence = Column(Float)  # 0.0 to 1.0
    predicted_score_home = Column(Integer)
    predicted_score_away = Column(Integer)
    
    # Model info
    model_version = Column(String(50))
    features_used = Column(Text)  # JSON with feature importance
    
    # Validation
    actual_winner = Column(Integer, ForeignKey('teams.id'))
    was_correct = Column(Boolean)
    
    # Metadata
    prediction_date = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_prediction_game', 'game_id'),
    )


class PerformanceStreak(Base):
    """Track hot/cold streaks for players"""
    __tablename__ = "performance_streaks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Streak info
    metric = Column(String(50))  # "pts", "fg3m", "ast", etc.
    streak_type = Column(String(10))  # "hot", "cold"
    threshold = Column(Float)
    
    # Streak stats
    current_streak = Column(Integer)  # Number of games
    streak_start_date = Column(Date)
    best_performance = Column(Float)
    avg_performance = Column(Float)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_streak_player', 'player_id', 'season'),
        Index('idx_streak_active', 'is_active'),
    )
