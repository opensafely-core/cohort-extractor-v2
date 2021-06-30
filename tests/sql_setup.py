from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class RegistrationHistory(Base):
    __tablename__ = "practice_registrations"
    RegistrationId = Column(Integer, primary_key=True)
    PatientId = Column(Integer)
    StpId = Column(String)


class Events(Base):
    __tablename__ = "events"
    EventId = Column(Integer, primary_key=True)
    PatientId = Column(Integer)
    EventCode = Column(String)
