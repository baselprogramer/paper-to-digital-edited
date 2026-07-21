"""نماذج قاعدة البيانات (تعمل مع MySQL و SQLite)."""
import datetime
from sqlalchemy import (create_engine, Column, Integer, String, Text, Float,
                        Boolean, DateTime, ForeignKey)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from werkzeug.security import generate_password_hash

import config as C

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True)
    password_hash = Column(String(255))


class Section(Base):
    __tablename__ = "sections"
    id = Column(Integer, primary_key=True)
    name = Column(String(120))
    description = Column(Text)
    template_path = Column(String(500), nullable=True)  # اختياري: بدونه = قسم Word فقط
    fields_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    documents = relationship("Document", back_populates="section",
                             order_by="Document.id.desc()")


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    filename = Column(String(255))
    output_mode = Column(String(20), default="per_page")
    total_pages = Column(Integer, default=0)
    status = Column(String(20), default="pending")
    needs_review = Column(Boolean, default=False)
    score = Column(Float, nullable=True)          # متوسط نسبة الدقة /100
    merged_json = Column(Text)
    output_path = Column(String(500))
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    section = relationship("Section", back_populates="documents")
    pages = relationship("Page", back_populates="document",
                         cascade="all, delete-orphan", order_by="Page.page_no")


class Page(Base):
    __tablename__ = "pages"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    page_no = Column(Integer)
    image_path = Column(String(500))
    raw_text = Column(Text)                        # نص Gemini الخام
    corrected_text = Column(Text)                  # النص بعد تدقيق Claude مع الصورة
    score = Column(Float, nullable=True)           # نسبة الدقة /100 لهذه الصفحة
    notes = Column(Text)                           # ملاحظات التدقيق البشري (JSON)
    structured_json = Column(Text)
    avg_conf = Column(Float)
    needs_review = Column(Boolean, default=False)
    status = Column(String(20), default="pending")
    document = relationship("Document", back_populates="pages")




class Correction(Base):
    """ذاكرة تعلم القسم: كل تصحيح بشري يُحفظ ويُحقن في تعليمات المعالجات القادمة."""
    __tablename__ = "corrections"
    id = Column(Integer, primary_key=True)
    section_id = Column(Integer, ForeignKey("sections.id"))
    kind = Column(String(20))                 # field | text
    label = Column(String(255), default="")   # اسم الحقل إن كان تصحيح حقل
    wrong = Column(Text)                      # ما قرأه النموذج
    right = Column(Text)                      # التصحيح البشري
    count = Column(Integer, default=1)        # عدد تكرار هذا التصحيح
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)


_engine = create_engine(
    C.DATABASE_URL, pool_pre_ping=True,
    connect_args=({"charset": "utf8mb4"} if C.DATABASE_URL.startswith("mysql")
                  else {"check_same_thread": False, "timeout": 30} if C.DATABASE_URL.startswith("sqlite")
                  else {}))
SessionLocal = sessionmaker(bind=_engine)


def init_db():
    Base.metadata.create_all(_engine)
    db = SessionLocal()
    if not db.query(User).filter_by(username=C.ADMIN_USER).first():
        db.add(User(username=C.ADMIN_USER,
                    password_hash=generate_password_hash(C.ADMIN_PASSWORD)))
        db.commit()
    db.close()
