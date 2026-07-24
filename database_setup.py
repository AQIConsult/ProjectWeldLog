import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean, Float
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///weld_log.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Weld(Base):
    __tablename__ = 'welds'
    id = Column(Integer, primary_key=True, index=True)
    weld_id = Column(String, unique=True, index=True, nullable=False)
    report_number = Column(String, nullable=False)
    inspection_date = Column(Date, nullable=False)
    
    spread = Column(Integer)
    weld_type = Column(String)
    rig_id = Column(String)
    weld_num_only = Column(String)
    
    suffix = Column(String, nullable=True)
    diameter = Column(Float, nullable=True)
    wall_thickness = Column(String, nullable=True)
    
    stationing = Column(String)
    nde_method = Column(String)
    result = Column(String)
    
    defect_type = Column(String)
    defect_start = Column(String, nullable=True)
    defect_length = Column(String, nullable=True)
    defect_depth = Column(String, nullable=True)
    defect_height = Column(String, nullable=True)
    
    welder_ids = Column(String, nullable=True)
    # --- NEW: Added comments column ---
    comments = Column(String, nullable=True)
    
    is_repair = Column(Boolean, default=False)
    is_delay_scan = Column(Boolean, default=False)
    
    repair_date = Column(Date, nullable=True)
    is_repaired = Column(Boolean, default=False)

def create_db():
    """Creates the database and the welds table if they don't exist."""
    Base.metadata.create_all(bind=engine)
    print("Database and table created successfully.")

if __name__ == "__main__":
    create_db()