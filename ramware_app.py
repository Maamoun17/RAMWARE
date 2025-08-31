# =====================
# IMPORTS
# =====================
import sys
import os
import math
import json
import sqlite3
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from PySide6.QtCore import Qt, QSize, QTranslator, QLocale, QDateTime, QTimer
from PySide6.QtGui import (QIcon, QAction, QColor, QPixmap, QPalette, QFont, 
                          QLinearGradient, QBrush, QPainter, QPen)
from PySide6.QtWidgets import (QApplication, QMainWindow, QStackedWidget, QWidget, 
                              QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                              QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
                              QHeaderView, QFileDialog, QFormLayout, QDoubleSpinBox, 
                              QDateEdit, QGroupBox, QTabWidget, QMessageBox, 
                              QToolBar, QStatusBar, QSplitter, QFrame, QSizePolicy,
                              QSpacerItem, QScrollArea, QAbstractItemView, QStyleFactory,
                              QInputDialog)  # Added QInputDialog here
from PySide6.QtWebEngineWidgets import QWebEngineView
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import tempfile

# =====================
# CONSTANTS & SETTINGS
# =====================
APP_NAME = "RamWare"
VERSION = "1.0.0"
AUTHOR = "Eng. Rami Maamoun"
COMPANY = "RamWare Engineering"
SUPPORT_EMAIL = "support@ramware.com"

# =====================
# CALCULATION ENGINE
# =====================
class WellTestCalculator:
    @staticmethod
    def calculate_oil_api_60f(oil_api, oil_temp):
        """Calculate Oil API at 60°F"""
        try:
            oil_temp = (oil_temp * 9/5) + 32  # Convert Celsius to Fahrenheit)
            
            if oil_temp <= 60:
                return oil_api
            else:
                delta_t = oil_temp - 60
                return oil_api - (0.00035 * delta_t * (oil_api - 10))
        except:
            return oil_api
    
    @staticmethod
    def calculate_vcf_sep(sep_temp, oil_api_60f):
        """Volume Correction Factor for separator conditions"""
        try:
            sep_temp = (sep_temp * 9/5) + 32  # Convert Celsius to Fahrenheit)
            delta_t = sep_temp - 60
            alpha = 0.00034878 - (0.00000091 * oil_api_60f)
            beta = 0.0000000025
            return math.exp(-(alpha * delta_t + beta * (delta_t ** 2)))
        except:
            return 1.0
    
    @staticmethod
    def calculate_shrinkage_factor(gor2, sep_p, oil_api_60f):
        """Calculate shrinkage factor with adjustments"""
        try:
            
            # Base C value based on API
            if oil_api_60f > 35:
                c = 0.00000025
            elif 25 <= oil_api_60f <= 35:
                c = 0.0000003
            else:  # oil_api_60f < 25
                c = 0.00000035
            
            # Adjustments for low GOR or low separator pressure
            if gor2 < 100 and sep_p < 50:
                c = 0.00000005
            elif gor2 < 100:
                c = 0.0000001
            elif sep_p < 50:
                c = 0.0000002
            
            return 1 - (c * gor2 * sep_p)
        except:
            return 1.0
    
    @staticmethod
    def calculate_gor2(oil_api_60f, sg_gas, sep_p, sep_temp, method='API'):
        """Calculate GOR2 based on selected method"""
        try:
            sep_p = sep_p + 14.7  # Convert to psia
            sep_temp = (sep_temp * 9/5) + 32  # Convert Celsius to Fahrenheit)
            if method == 'API':
                # API-based correlation selection
                if oil_api_60f > 35:
                    return WellTestCalculator._vasquez_beggs(sg_gas, sep_p, oil_api_60f, sep_temp)
                elif 25 <= oil_api_60f <= 35:
                    return WellTestCalculator._standings(sg_gas, sep_p, oil_api_60f, sep_temp)
                else:  # oil_api_60f < 25
                    return WellTestCalculator._katz(sg_gas, sep_p, oil_api_60f, sep_temp)
            
            elif method == 'VASQUEZ_BEGGS':
                # Vasquez-Beggs with API-dependent coefficients
                sep_p = sep_p + 14.7  # Convert to psia
                sep_temp = (sep_temp * 9/5) + 32  # Convert Celsius to Fahrenheit)
                if oil_api_60f <= 30:
                    return WellTestCalculator._vasquez_beggs(sg_gas, sep_p, oil_api_60f, sep_temp, 
                                                            c1=0.0362, c2=1.0937, c3=25.724)
                else:
                    return WellTestCalculator._vasquez_beggs(sg_gas, sep_p, oil_api_60f, sep_temp, 
                                                            c1=0.0178, c2=1.1870, c3=23.931)
            
            elif method == 'STANDINGS':
                return WellTestCalculator._standings(sg_gas, sep_p, oil_api_60f, sep_temp)
            
            elif method == 'KATZ':
                return WellTestCalculator._katz(sg_gas, sep_p, oil_api_60f, sep_temp)
            
            else:
                return 0.0
        except:
            return 0.0
    
    @staticmethod
    def _vasquez_beggs(sg_gas, sep_p, oil_api_60f, sep_temp, c1=0.0178, c2=1.1870, c3=23.931):
        """Vasquez-Beggs correlation"""
        try:
            sep_p = sep_p + 14.7  # Convert to psia
            sep_temp = (sep_temp * 9/5) + 32  # Convert Celsius to Fahrenheit)
            return sg_gas * c1 * (sep_p ** c2) * math.exp(c3 * oil_api_60f / (sep_temp + 460))
        except:
            return 0.0
    
    @staticmethod
    def _standings(sg_gas, sep_p, oil_api_60f, sep_temp):
        """Standing's correlation"""
        try:
            sep_p = sep_p + 14.7  # Convert to psia
            exponent = 0.0125 * oil_api_60f - 0.00091 * sep_temp
            return sg_gas * ((sep_p * (10 ** exponent)) / 18.2) ** 1.204
        except:
            return 0.0
    
    @staticmethod
    def _katz(sg_gas, sep_p, oil_api_60f, sep_temp):
        """Katz correlation"""
        try:
            sep_p = sep_p + 14.7  # Convert to psia
            exponent = 0.01245 * oil_api_60f - 0.00091 * sep_temp
            return 0.224 * sg_gas * (sep_p ** 1.182) * (10 ** exponent)
        except:
            return 0.0
    
    @staticmethod
    def calculate_gas_flow(hw, sep_p, gas_t, sg_gas, orifice_d, line_bore, h2s, co2):
        """Calculate gas flow rate using orifice equation"""
        try:
            # 1. Basic orifice factor (Fb)
            beta = orifice_d / line_bore
            cd = 0.5959 + 0.0312 * (beta ** 2.1) - 0.1840 * (beta ** 8)
            fb = (338.17 * (orifice_d ** 2) * cd) / math.sqrt(1 - beta ** 4)
            
            # 2. Specific gravity factor (Fg)
            fg = 1 / math.sqrt(sg_gas)
            
            # 3. Absolute pressure
            pf = sep_p + 14.7
            
            # 4. Expansion factor (Y2)
            delta_p_psi = hw * 0.03613
            p1 = pf + delta_p_psi  # Upstream pressure
            y2 = 1 - ((0.41 + 0.35 * beta ** 4) * delta_p_psi) / (1.28 * p1)
            
            # 5. Flowing temperature factor (Ftf)
            ftf = math.sqrt(520 / (gas_t + 460))
            
            # 6. Supercompressibility factor (Fpv)
            fpv = WellTestCalculator.calculate_fpv(sg_gas, p1, gas_t, h2s, co2)
            
            # 7. Calculate gas flow
            q_gas = (24 * fb * fg * y2 * ftf * fpv * math.sqrt(hw * pf)) / 1000
            
            return q_gas
        except:
            return 0.0
    
    @staticmethod
    def calculate_fpv(sg_gas, p, t, h2s, co2):
        """Calculate supercompressibility factor with Wichert-Aziz correction"""
        try:
            # Convert ppm to mole fractions
            y_h2s = h2s / 1e6
            y_co2 = co2 / 1e6
            
            # Pseudo-critical properties (Sutton's method)
            tpc = 168 + (325 * sg_gas) - (12.5 * (sg_gas ** 2))
            ppc = 677 + (15 * sg_gas) - (37.5 * (sg_gas ** 2))
            
            # Wichert-Aziz correction
            a = y_h2s + y_co2
            epsilon = 120 * (a ** 0.9 - a ** 1.6) + 15 * (y_h2s ** 0.5 - y_h2s ** 4)
            tpc_corr = tpc - epsilon
            ppc_corr = (ppc * tpc_corr) / (tpc + y_h2s * (1 - y_h2s) * epsilon)
            
            # Pseudo-reduced properties
            tpr = (t + 460) / tpc_corr
            ppr = p / ppc_corr
            
            # Compressibility factor (Papay equation)
            z = 1 - (3.52 * ppr) / (10 ** (0.9813 * tpr)) + (0.274 * (ppr ** 2)) / (10 ** (0.8157 * tpr))
            
            # Supercompressibility factor
            return 1 / math.sqrt(z)
        except:
            return 1.0
    
    @staticmethod
    def calculate_three_phase_flow(vs_oil, vs_water, wio, meter_factor, sf, vcf_sep):
        """Calculate flow rates for three-phase separation"""
        try:
            q_oil = vs_oil * (1 - wio) * meter_factor * sf * vcf_sep * 48
            q_water = ((vs_water * meter_factor) + (vs_oil * wio)) * 48
            return q_oil, q_water
        except:
            return 0.0, 0.0
    
    @staticmethod
    def calculate_two_phase_flow(vs_liquid, bsw, meter_factor, sf, vcf_sep):
        """Calculate flow rates for two-phase separation"""
        try:
            q_oil = vs_liquid * (1 - bsw) * meter_factor * sf * vcf_sep * 48
            q_water = vs_liquid * meter_factor * bsw * 48
            return q_oil, q_water
        except:
            return 0.0, 0.0
    
    @staticmethod
    def calculate_for_gas_lift(q_gas, q_gas_inj, q_oil, gor2):
        """Calculate Gas Lift specific metrics"""
        try:
            formation_q_gas = max(q_gas - q_gas_inj, 0)
            gor1_formation = (formation_q_gas * 1000) / q_oil if q_oil > 0 else 0
            total_gor_formation = gor1_formation + gor2
            return formation_q_gas, gor1_formation, total_gor_formation
        except:
            return 0.0, 0.0, 0.0

# =====================
# DATABASE MANAGER
# =====================
class DatabaseManager:
    def __init__(self):
        self.db_path = os.path.join(os.path.expanduser("~"), "RamWare", "ramware.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Connect to SQLite database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            return True
        except sqlite3.Error as e:
            print(f"Database connection error: {str(e)}")
            return False
    
    def create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            cursor = self.conn.cursor()
            
            # Projects table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    data TEXT
                )
            ''')
            
            # User settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'en',
                    theme TEXT DEFAULT 'dark',
                    unit_system TEXT DEFAULT 'imperial',
                    last_project INTEGER
                )
            ''')
            
            # Insert default settings if not exists
            cursor.execute('''
                INSERT OR IGNORE INTO settings (id, language, theme, unit_system) 
                VALUES (1, 'en', 'dark', 'imperial')
            ''')
            
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error creating tables: {str(e)}")
            return False
    
    def save_project(self, project_data):
        """Save project to database"""
        try:
            cursor = self.conn.cursor()
            data_json = json.dumps(project_data)
            
            if 'id' in project_data and project_data['id']:
                # Update existing project
                cursor.execute('''
                    UPDATE projects 
                    SET name = ?, data = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (project_data['name'], data_json, project_data['id']))
            else:
                # Insert new project
                cursor.execute('''
                    INSERT INTO projects (name, data)
                    VALUES (?, ?)
                ''', (project_data['name'], data_json))
                project_data['id'] = cursor.lastrowid
            
            self.conn.commit()
            return project_data
        except sqlite3.Error as e:
            print(f"Error saving project: {str(e)}")
            return None
    
    def load_project(self, project_id):
        """Load project from database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, name, created_at, updated_at, data
                FROM projects
                WHERE id = ?
            ''', (project_id,))
            row = cursor.fetchone()
            
            if row:
                project_data = json.loads(row[4])
                project_data.update({
                    'id': row[0],
                    'name': row[1],
                    'created_at': row[2],
                    'updated_at': row[3]
                })
                return project_data
            return None
        except sqlite3.Error as e:
            print(f"Error loading project: {str(e)}")
            return None
    
    def list_projects(self):
        """List all projects"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, name, created_at, updated_at
                FROM projects
                ORDER BY updated_at DESC
            ''')
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error listing projects: {str(e)}")
            return []
    
    def get_settings(self):
        """Get user settings"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT language, theme, unit_system, last_project FROM settings WHERE id = 1')
            row = cursor.fetchone()
            if row:
                return {
                    'language': row[0],
                    'theme': row[1],
                    'unit_system': row[2],
                    'last_project': row[3]
                }
            return None
        except sqlite3.Error as e:
            print(f"Error getting settings: {str(e)}")
            return None
    
    def save_settings(self, settings):
        """Save user settings"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE settings
                SET language = ?, theme = ?, unit_system = ?, last_project = ?
                WHERE id = 1
            ''', (
                settings.get('language', 'en'),
                settings.get('theme', 'dark'),
                settings.get('unit_system', 'imperial'),
                settings.get('last_project')
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error saving settings: {str(e)}")
            return False

# =====================
# UI COMPONENTS
# =====================
class GradientButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(40)
        self.setFont(QFont("Arial", 10, QFont.Bold))
        self._gradient = QLinearGradient(0, 0, 0, self.height())
        self._gradient.setColorAt(0, QColor("#3498db"))
        self._gradient.setColorAt(1, QColor("#2980b9"))
        self._text_color = QColor("#ffffff")
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background
        painter.setBrush(QBrush(self._gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 5, 5)
        
        # Draw text
        painter.setPen(QPen(self._text_color))
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())
        
    def setGradient(self, start_color, end_color):
        self._gradient = QLinearGradient(0, 0, 0, self.height())
        self._gradient.setColorAt(0, start_color)
        self._gradient.setColorAt(1, end_color)
        self.update()
        
    def setTextColor(self, color):
        self._text_color = color
        self.update()

class DashboardPage(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        
    def setup_ui(self):
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(50, 30, 50, 30)
        main_layout.setSpacing(30)
        
  
        # Header (Logo only, no text title)
        header_layout = QHBoxLayout()
        logo = QLabel()
        pixmap = QPixmap(":/icons/logo.png")
        if pixmap.isNull():
            pixmap = QPixmap("logo.png")  # fallback if resource path fails
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignCenter)
        logo.setScaledContents(True)  # Allow the pixmap to scale with the label
        logo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # Expanding
        logo.setMaximumHeight(400)    # Set your preferred max height

        header_layout.addWidget(logo, alignment=Qt.AlignCenter)
        
        # Logo
        logo = QLabel()
        pixmap = QPixmap(":/icons/logo.png").scaledToHeight(400)
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignCenter)
        
        # Buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(20)
        button_layout.setContentsMargins(100, 0, 100, 0)
        
        self.new_test_btn = GradientButton("Create New Test")
        self.new_test_btn.setGradient(QColor("#2ecc71"), QColor("#27ae60"))
        self.new_test_btn.clicked.connect(self.parent.create_new_test)
        
        self.open_test_btn = GradientButton("Open Existing Test")
        self.open_test_btn.setGradient(QColor("#3498db"), QColor("#2980b9"))
        self.open_test_btn.clicked.connect(self.parent.open_project_dialog)
        
        self.tutorials_btn = GradientButton("Tutorials")
        self.tutorials_btn.setGradient(QColor("#9b59b6"), QColor("#8e44ad"))
        self.tutorials_btn.clicked.connect(self.parent.show_tutorials)
        
        button_layout.addWidget(self.new_test_btn)
        button_layout.addWidget(self.open_test_btn)
        button_layout.addWidget(self.tutorials_btn)
        
        # Recent projects
        recent_group = QGroupBox("Recent Projects")
        recent_layout = QVBoxLayout()
        
        self.recent_list = QComboBox()
        self.recent_list.setMinimumHeight(35)
        recent_layout.addWidget(self.recent_list)
        
        open_recent_btn = GradientButton("Open Selected Project")
        open_recent_btn.setGradient(QColor("#f39c12"), QColor("#d35400"))
        open_recent_btn.clicked.connect(self.open_recent_project)
        recent_layout.addWidget(open_recent_btn)
        
        recent_group.setLayout(recent_layout)
        
        # Footer
        footer = QLabel(f"© {datetime.now().year} {COMPANY} | Version {VERSION}")
        footer.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        footer.setAlignment(Qt.AlignCenter)
        
        # Add to main layout
        main_layout.addLayout(header_layout)
        main_layout.addWidget(logo, alignment=Qt.AlignCenter)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)
        main_layout.addStretch(1)
        main_layout.addWidget(recent_group)
        main_layout.addStretch(1)
        main_layout.addWidget(footer)
        
        self.setLayout(main_layout)
    
    def load_recent_projects(self):
        """Load recent projects from database"""
        self.recent_list.clear()
        projects = self.parent.db.list_projects()
        for project in projects:
            self.recent_list.addItem(f"{project[1]} ({project[3][:10]})", project[0])
    
    def open_recent_project(self):
        """Open the selected recent project"""
        project_id = self.recent_list.currentData()
        if project_id:
            self.parent.load_project(project_id)

class ParametersPage(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        
    def setup_ui(self):
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 10, 20, 20)
        
        # Create a scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Well Information
        well_group = QGroupBox("Well Information")
        well_layout = QFormLayout()
        well_layout.setHorizontalSpacing(20)
        well_layout.setVerticalSpacing(10)
        
        self.field_name = QLineEdit()
        self.test_date = QDateEdit()
        self.test_date.setCalendarPopup(True)
        self.test_date.setDate(datetime.now().date())
        self.well_name = QLineEdit()
        
        well_layout.addRow("Field Name:", self.field_name)
        well_layout.addRow("Test Date:", self.test_date)
        well_layout.addRow("Well Name:", self.well_name)
        well_group.setLayout(well_layout)
        
        # Fluid Properties
        fluid_group = QGroupBox("Fluid Properties")
        fluid_layout = QFormLayout()
        fluid_layout.setHorizontalSpacing(20)
        fluid_layout.setVerticalSpacing(10)
        
        self.oil_api = QDoubleSpinBox()
        self.oil_api.setRange(0, 100)
        self.oil_api.setValue(30)
        self.oil_temp = QDoubleSpinBox()
        self.oil_temp.setRange(-50, 300)
        self.oil_temp.setValue(60)
        self.salinity = QDoubleSpinBox()
        self.salinity.setRange(0, 1000000)
        self.salinity.setValue(50000)
        self.meter_factor = QDoubleSpinBox()
        self.meter_factor.setRange(0.5, 1.5)
        self.meter_factor.setValue(1.0)
        
        fluid_layout.addRow("Oil API obs:", self.oil_api)
        fluid_layout.addRow("Oil Temperature obs (°C):", self.oil_temp)
        fluid_layout.addRow("Salinity (PPM):", self.salinity)
        fluid_layout.addRow("Meter Factor:", self.meter_factor)
        fluid_group.setLayout(fluid_layout)
        
        # Well & Separator Configuration
        config_group = QGroupBox("Well & Separator Configuration")
        config_layout = QFormLayout()
        config_layout.setHorizontalSpacing(20)
        config_layout.setVerticalSpacing(10)
        
        self.production_type = QComboBox()
        self.production_type.addItems(["NATURAL FLOW", "GAS LIFT", "ESP"])
        self.separation_type = QComboBox()
        self.separation_type.addItems(["THREE PHASES", "TWO PHASES"])
        self.flow_type = QComboBox()
        self.flow_type.addItems(["TUBING", "ANNULUS"])
        self.gor2_method = QComboBox()
        self.gor2_method.addItems(["API", "KATZ", "VASQUEZ BEGGS", "STANDING'S"])
        
        config_layout.addRow("Production Type:", self.production_type)
        config_layout.addRow("Separation Type:", self.separation_type)
        config_layout.addRow("Flow Type:", self.flow_type)
        config_layout.addRow("GOR2 Method:", self.gor2_method)
        config_group.setLayout(config_layout)
        
        # Gas Measurement
        gas_group = QGroupBox("Gas Measurement")
        gas_layout = QFormLayout()
        gas_layout.setHorizontalSpacing(20)
        gas_layout.setVerticalSpacing(10)
        
        self.line_bore = QDoubleSpinBox()
        self.line_bore.setRange(0.1, 100)
        self.line_bore.setValue(4.0)
        self.dp_range = QComboBox()
        self.dp_range.addItems(["0-100", "0-200", "0-300", "0-400"])
        self.h2s = QDoubleSpinBox()
        self.h2s.setRange(0, 1000000)
        self.co2 = QDoubleSpinBox()
        self.co2.setRange(0, 1000000)
        self.n2 = QDoubleSpinBox()
        self.n2.setRange(0, 1000000)
        self.orifice_diameter = QDoubleSpinBox()
        self.orifice_diameter.setRange(0.1, 100)
        self.orifice_diameter.setValue(2.0)
        self.pressure_range = QComboBox()
        self.pressure_range.addItems(["0-1000", "0-1500", "0-2000"])
        self.sg_gas = QDoubleSpinBox()
        self.sg_gas.setRange(0.1, 2.0)
        self.sg_gas.setValue(0.65)
        
        gas_layout.addRow("Line Bore (ID) (in):", self.line_bore)
        gas_layout.addRow("DP Range (inH₂O):", self.dp_range)
        gas_layout.addRow("H₂S (PPM):", self.h2s)
        gas_layout.addRow("CO₂ (PPM):", self.co2)
        gas_layout.addRow("N₂ (PPM):", self.n2)
        gas_layout.addRow("Orifice Diameter (in):", self.orifice_diameter)
        gas_layout.addRow("Pressure Range (PSI):", self.pressure_range)
        gas_layout.addRow("SG Gas:", self.sg_gas)
        gas_group.setLayout(gas_layout)
        
        # Gas Injection Line
        self.gas_inj_group = QGroupBox("Gas Injection Line")
        gas_inj_layout = QFormLayout()
        gas_inj_layout.setHorizontalSpacing(20)
        gas_inj_layout.setVerticalSpacing(10)
        
        self.gas_inj_coeff = QDoubleSpinBox()
        self.gas_inj_coeff.setRange(0, 10)
        self.gas_inj_coeff.setValue(1.0)
        self.gas_inj_orifice = QDoubleSpinBox()
        self.gas_inj_orifice.setRange(0.1, 10)
        self.gas_inj_orifice.setValue(1.5)
        
        gas_inj_layout.addRow("Coefficient:", self.gas_inj_coeff)
        gas_inj_layout.addRow("Orifice Plate (in):", self.gas_inj_orifice)
        self.gas_inj_group.setLayout(gas_inj_layout)
        self.gas_inj_group.setVisible(False)
        
        # Connect production type change
        self.production_type.currentTextChanged.connect(self.toggle_gas_inj)
        
        # Add groups to scroll layout
        scroll_layout.addWidget(well_group)
        scroll_layout.addWidget(fluid_group)
        scroll_layout.addWidget(config_group)
        scroll_layout.addWidget(gas_group)
        scroll_layout.addWidget(self.gas_inj_group)
        scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_content)
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        self.cancel_btn = GradientButton("Cancel")
        self.cancel_btn.setGradient(QColor("#e74c3c"), QColor("#c0392b"))
        self.cancel_btn.clicked.connect(lambda: self.parent.show_page("DASHBOARD"))
        self.save_btn = GradientButton("Save & Continue")
        self.save_btn.setGradient(QColor("#2ecc71"), QColor("#27ae60"))
        self.save_btn.clicked.connect(self.save_parameters)
        
        nav_layout.addWidget(self.cancel_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.save_btn)
        
        # Add to main layout
        main_layout.addWidget(scroll_area)
        main_layout.addLayout(nav_layout)
        
        self.setLayout(main_layout)
    
    def toggle_gas_inj(self, production_type):
        self.gas_inj_group.setVisible(production_type == "GAS LIFT")
    
    def save_parameters(self):
        # Save parameters to project
        params = {
            "field_name": self.field_name.text(),
            "test_date": self.test_date.date().toString("yyyy-MM-dd"),
            "well_name": self.well_name.text(),
            "oil_api": self.oil_api.value(),
            "oil_temp": self.oil_temp.value(),
            "salinity": self.salinity.value(),
            "meter_factor": self.meter_factor.value(),
            "production_type": self.production_type.currentText(),
            "separation_type": self.separation_type.currentText(),
            "flow_type": self.flow_type.currentText(),
            "gor2_method": self.gor2_method.currentText(),
            "line_bore": self.line_bore.value(),
            "dp_range": self.dp_range.currentText(),
            "h2s": self.h2s.value(),
            "co2": self.co2.value(),
            "n2": self.n2.value(),
            "orifice_diameter": self.orifice_diameter.value(),
            "pressure_range": self.pressure_range.currentText(),
            "sg_gas": self.sg_gas.value(),
            "gas_inj_coeff": self.gas_inj_coeff.value() if self.production_type.currentText() == "GAS LIFT" else 0,
            "gas_inj_orifice": self.gas_inj_orifice.value() if self.production_type.currentText() == "GAS LIFT" else 0
        }
        
        self.parent.current_project["parameters"] = params
        self.parent.show_page("DATA_ENTRY")

class DataEntryPage(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 10, 20, 20)
        
        # Header
        header_layout = QHBoxLayout()
        self.title = QLabel("Data Entry")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.import_btn = GradientButton("Import from Excel")
        self.import_btn.setGradient(QColor("#3498db"), QColor("#2980b9"))
        self.import_btn.clicked.connect(self.import_from_excel)
        
        header_layout.addWidget(self.title)
        header_layout.addStretch()
        header_layout.addWidget(self.import_btn)
        
        # Data table
        self.table = QTableWidget()
        self.table.setRowCount(12)  # 6 hours * 30 min intervals
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                alternate-background-color: #171515;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: white;
                padding: 4px;
                border: 1px solid #1a2a3a;
            }
        """)
        
        # Navigation
        nav_layout = QHBoxLayout()
        self.back_btn = GradientButton("Back")
        self.back_btn.setGradient(QColor("#95a5a6"), QColor("#7f8c8d"))
        self.back_btn.clicked.connect(lambda: self.parent.show_page("PARAMETERS"))
        self.calculate_btn = GradientButton("Calculate Results")
        self.calculate_btn.setGradient(QColor("#2ecc71"), QColor("#27ae60"))
        self.calculate_btn.clicked.connect(self.calculate_results)
        
        nav_layout.addWidget(self.back_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.calculate_btn)
        
        layout.addLayout(header_layout)
        layout.addWidget(self.table, 1)
        layout.addLayout(nav_layout)
        
        self.setLayout(layout)
    
    def setup_table(self):
        params = self.parent.current_project["parameters"]
        separation_type = params["separation_type"]
        production_type = params["production_type"]
        
        self.table.clear()
        self.table.setColumnCount(0)
        
        columns = ["Time", "Choke", "WHP (PSIG)", "WHT (°C)", "Casing (PSIG)", 
                   "SEP P (PSIG)", "GAS T (°C)", "Oil Outlet P (PSIG)", "Oil T (°C)"]
        
        if separation_type == "THREE PHASES":
            columns.extend(["Meter Oil (BBL)", "Meter Water (BBL)", "WIO (%)"])
        else:
            columns.extend(["Meter Liquid (BBL)", "BSW (%)"])
        
        columns.append("GAS DP (inH₂O)")
        
        if production_type == "GAS LIFT":
            columns.append("Q Gas Inj (MSCF/D)")
        
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # Set column widths
        for i in range(len(columns)):
            self.table.setColumnWidth(i, 120)
        
        # Set initial time values
        for i in range(12):
            hours = i // 2
            minutes = 30 * (i % 2)
            time_item = QTableWidgetItem(f"{hours:02d}:{minutes:02d}")
            # time_item.setFlags(time_item.flags() ^ Qt.ItemIsEditable)  # Allow editing
            self.table.setItem(i, 0, time_item)
        
        # Set initial values for meters
        start_col = 9 if separation_type == "THREE PHASES" else 8
        for i in range(12):
            zero_item = QTableWidgetItem("0.0")
            self.table.setItem(i, start_col, zero_item)
    
    def import_from_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Excel File", "", "Excel Files (*.xlsx *.xls)"
        )
        
        if file_path:
            try:
                df = pd.read_excel(file_path)
                # Process and populate table
                QMessageBox.information(self, "Import Successful", "Data imported successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import data: {str(e)}")
    
    def calculate_results(self):
        # Collect and validate data
        data = []
        valid = True
        errors = []
        
        for row in range(self.table.rowCount()):
            row_data = {}
            for col in range(self.table.columnCount()):
                header = self.table.horizontalHeaderItem(col).text()
                item = self.table.item(row, col)
                
                if item and item.text():
                    try:
                        # Skip time column
                        if header == "Time":
                            row_data[header] = item.text()
                        else:
                            row_data[header] = float(item.text())
                    except:
                        errors.append(f"Invalid number in row {row+1}, column '{header}'")
                        valid = False
                else:
                    if col > 0:  # Skip time column
                        errors.append(f"Missing value in row {row+1}, column '{header}'")
                        valid = False
                        row_data[header] = 0.0
            
            data.append(row_data)
        
        if not valid:
            QMessageBox.critical(self, "Data Error", "\n".join(errors))
            return
        
        self.parent.current_project["time_series"] = data
        self.parent.perform_calculations()
        self.parent.show_page("RESULTS")

class ResultsPage(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 10, 20, 20)
        
        # Header
        header_layout = QHBoxLayout()
        self.title = QLabel("Test Results")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.export_btn = GradientButton("Export to PDF")
        self.export_btn.setGradient(QColor("#e74c3c"), QColor("#c0392b"))
        self.export_btn.clicked.connect(self.parent.export_report)
        
        header_layout.addWidget(self.title)
        header_layout.addStretch()
        header_layout.addWidget(self.export_btn)
        
        # Results table
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                alternate-background-color: #171515;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: white;
                padding: 4px;
                border: 1px solid #1a2a3a;
            }
        """)
        
        # Navigation
        nav_layout = QHBoxLayout()
        self.back_btn = GradientButton("Back to Data")
        self.back_btn.setGradient(QColor("#95a5a6"), QColor("#7f8c8d"))
        self.back_btn.clicked.connect(lambda: self.parent.show_page("DATA_ENTRY"))
        self.plots_btn = GradientButton("View Plots")
        self.plots_btn.setGradient(QColor("#9b59b6"), QColor("#8e44ad"))
        self.plots_btn.clicked.connect(lambda: self.parent.show_page("PLOTS"))
        
        nav_layout.addWidget(self.back_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.plots_btn)
        
        layout.addLayout(header_layout)
        layout.addWidget(self.table, 1)
        layout.addLayout(nav_layout)
        
        self.setLayout(layout)
    
    def display_results(self):
        results = self.parent.current_project["results"]
        if not results:
            return
        
        # Determine columns based on production type
        production_type = self.parent.current_project["parameters"]["production_type"]
        
        columns = ["Time", "Q Oil (BBL/D)", "Q Water (BBL/D)", "Total Q (BBL/D)"]
        
        if production_type == "GAS LIFT":
            columns.extend([
                "Q Gas (MSCF/D)", "Formation Gas (MSCF/D)", "GOR1 (SCF/STB)", 
                "GOR1 Formation (SCF/STB)", "GOR2 (SCF/STB)", "Total GOR Formation (SCF/STB)", "Total GOR (SCF/STB)"
            ])
        else:
            columns.extend([
                "Q Gas (MSCF/D)", "GOR1 (SCF/STB)", "GOR2 (SCF/STB)", "Total GOR (SCF/STB)"
            ])
        
        self.table.setRowCount(len(results))
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # Set column widths
        for i in range(len(columns)):
            self.table.setColumnWidth(i, 150)
        
        # Populate table
        for row_idx, result in enumerate(results):
            self.table.setItem(row_idx, 0, QTableWidgetItem(result["Time"]))
            self.table.setItem(row_idx, 1, QTableWidgetItem(f"{result['Q Oil']:.2f}"))
            self.table.setItem(row_idx, 2, QTableWidgetItem(f"{result['Q Water']:.2f}"))
            self.table.setItem(row_idx, 3, QTableWidgetItem(f"{result['Total Q']:.2f}"))
            
            if production_type == "GAS LIFT":
                self.table.setItem(row_idx, 4, QTableWidgetItem(f"{result['Q Gas']:.2f}"))
                self.table.setItem(row_idx, 5, QTableWidgetItem(f"{result['Formation Gas']:.2f}"))
                self.table.setItem(row_idx, 6, QTableWidgetItem(f"{result['GOR1']:.2f}"))
                self.table.setItem(row_idx, 7, QTableWidgetItem(f"{result['GOR1 Formation']:.1f}"))
                self.table.setItem(row_idx, 8, QTableWidgetItem(f"{result['GOR2']:.1f}"))
                self.table.setItem(row_idx, 9, QTableWidgetItem(f"{result['Total GOR Formation']:.1f}"))
                self.table.setItem(row_idx, 10, QTableWidgetItem(f"{result['Total GOR']:.1f}"))
            else:
                self.table.setItem(row_idx, 4, QTableWidgetItem(f"{result['Q Gas']:.2f}"))
                self.table.setItem(row_idx, 5, QTableWidgetItem(f"{result['GOR1']:.1f}"))
                self.table.setItem(row_idx, 6, QTableWidgetItem(f"{result['GOR2']:.1f}"))
                self.table.setItem(row_idx, 7, QTableWidgetItem(f"{result['Total GOR']:.1f}"))
        
        # Add averages row
        averages = self.parent.current_project["averages"]
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)
        self.table.setItem(row_idx, 0, QTableWidgetItem("AVERAGE"))
        
        self.table.setItem(row_idx, 1, QTableWidgetItem(f"{averages.get('Q Oil', 0):.2f}"))
        self.table.setItem(row_idx, 2, QTableWidgetItem(f"{averages.get('Q Water', 0):.2f}"))
        self.table.setItem(row_idx, 3, QTableWidgetItem(f"{averages.get('Total Q', 0):.2f}"))
        
        if production_type == "GAS LIFT":
            self.table.setItem(row_idx, 4, QTableWidgetItem(f"{averages.get('Q Gas', 0):.2f}"))
            self.table.setItem(row_idx, 5, QTableWidgetItem(f"{averages.get('Formation Gas', 0):.2f}"))
            self.table.setItem(row_idx, 6, QTableWidgetItem(f"{averages.get('GOR1', 0):.2f}"))
            self.table.setItem(row_idx, 7, QTableWidgetItem(f"{averages.get('GOR1 Formation', 0):.1f}"))
            self.table.setItem(row_idx, 8, QTableWidgetItem(f"{averages.get('GOR2', 0):.1f}"))
            self.table.setItem(row_idx, 9, QTableWidgetItem(f"{averages.get('Total GOR Formation', 0):.1f}"))
            self.table.setItem(row_idx, 10, QTableWidgetItem(f"{averages.get('Total GOR', 0):.1f}"))
        else:
            self.table.setItem(row_idx, 4, QTableWidgetItem(f"{averages.get('Q Gas', 0):.2f}"))
            self.table.setItem(row_idx, 5, QTableWidgetItem(f"{averages.get('GOR1', 0):.1f}"))
            self.table.setItem(row_idx, 6, QTableWidgetItem(f"{averages.get('GOR2', 0):.1f}"))
            self.table.setItem(row_idx, 7, QTableWidgetItem(f"{averages.get('Total GOR', 0):.1f}"))
        
        # Set hexviolet background for averages row
        for col in range(self.table.columnCount()):
            item = self.table.item(row_idx, col)
            if item:
                item.setBackground(QColor(67, 32, 136))

class PlotsPage(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 10, 20, 20)
        
        # Header
        header_layout = QHBoxLayout()
        self.title = QLabel("Test Plots")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        header_layout.addWidget(self.title)
        header_layout.addStretch()
        
        # Plot type selection
        self.plot_type = QComboBox()
        self.plot_type.addItems([
            "Production Rates", 
            "Gas Rates", 
            "GOR Analysis",
            "Pressure Analysis"
        ])
        self.plot_type.currentIndexChanged.connect(self.update_plot)
        header_layout.addWidget(QLabel("Plot Type:"))
        header_layout.addWidget(self.plot_type)
        
        layout.addLayout(header_layout)
        
        # Plot container
        self.plot_container = QWidget()
        plot_layout = QVBoxLayout(self.plot_container)
        
        # Navigation
        nav_layout = QHBoxLayout()
        self.back_btn = GradientButton("Back to Results")
        self.back_btn.setGradient(QColor("#95a5a6"), QColor("#7f8c8d"))
        self.back_btn.clicked.connect(lambda: self.parent.show_page("RESULTS"))
        
        nav_layout.addWidget(self.back_btn)
        nav_layout.addStretch()
        
        layout.addWidget(self.plot_container, 1)
        layout.addLayout(nav_layout)
        
        self.setLayout(layout)
    
    def update_plot(self):
        # Clear previous plot
        for i in reversed(range(self.plot_container.layout().count())):
            widget = self.plot_container.layout().itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Create new plot
        plot_type = self.plot_type.currentText()
        if plot_type == "Production Rates":
            self.create_production_plot()
        elif plot_type == "Gas Rates":
            self.create_gas_plot()
        elif plot_type == "GOR Analysis":
            self.create_gor_plot()
        elif plot_type == "Pressure Analysis":
            self.create_pressure_plot()
    
    def create_production_plot(self):
        results = self.parent.current_project["results"]
        if not results:
            return
        
        # Create figure
        fig = Figure(figsize=(10, 6))
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        
        # Extract data
        times = [result["Time"] for result in results]
        q_oil = [result["Q Oil"] for result in results]
        q_water = [result["Q Water"] for result in results]
        total_q = [result["Total Q"] for result in results]
        
        # Plot data
        ax.plot(times, q_oil, 'b-o', label='Q Oil (BBL/D)')
        ax.plot(times, q_water, 'g--s', label='Q Water (BBL/D)')
        ax.plot(times, total_q, 'r-^', label='Total Q (BBL/D)')
        
        # Format plot
        ax.set_title('Production Rates Over Time')
        ax.set_xlabel('Time')
        ax.set_ylabel('Rate (BBL/D)')
        ax.legend()
        ax.grid(True)
        
        # Add to layout
        self.plot_container.layout().addWidget(canvas)
        canvas.draw()
    
    def create_gas_plot(self):
        results = self.parent.current_project["results"]
        if not results:
            return
        
        # Create figure
        fig = Figure(figsize=(10, 6))
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        
        # Extract data
        times = [result["Time"] for result in results]
        q_gas = [result["Q Gas"] for result in results]
                
        # Plot data
        ax.plot(times, q_gas, 'b-o', label='Q Gas (MSCF/D)')
               
        # Format plot
        ax.set_title('GAS Rates Over Time')
        ax.set_xlabel('Time')
        ax.set_ylabel('Rate (MSCF/D)')
        ax.legend()
        ax.grid(True)
        
        # Add to layout
        self.plot_container.layout().addWidget(canvas)
        canvas.draw()
    
    def create_gor_plot(self):
        results = self.parent.current_project["results"]
        if not results:
            return
        
        # Create figure
        fig = Figure(figsize=(10, 6))
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        
        # Extract data
        times = [result["Time"] for result in results]
        gor1 = [result["GOR1"] for result in results]
        gor2 = [result["GOR2"] for result in results]
        total_gor = [result["Total GOR"] for result in results]
        
        # Plot data
        ax.plot(times, gor1, 'b-o', label='GOR1 (SCF/STB)')
        ax.plot(times, gor2, 'g--s', label='GOR2 (SCF/STB)')
        ax.plot(times, total_gor, 'r-^', label='Total GOR (SCF/STB)')
        
        # Format plot
        ax.set_title('GOR Rates Over Time')
        ax.set_xlabel('Time')
        ax.set_ylabel('Rate (SCF/STB)')
        ax.legend()
        ax.grid(True)
        
        # Add to layout
        self.plot_container.layout().addWidget(canvas)
        canvas.draw()
    
    def create_pressure_plot(self):
        # Similar implementation for pressure plots
        pass

# =====================
# APPLICATION STARTUP
# =====================
class RamWareApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RamWare - Well Testing Software")
        self.setGeometry(100, 100, 1280, 800)
        
        # Initialize database
        self.db = DatabaseManager()
        
        # Load settings
        self.settings = self.db.get_settings() or {
            'language': 'en',
            'theme': 'dark',
            'unit_system': 'imperial',
            'last_project': None
        }
        
        # Initialize project
        self.current_project = {
            'id': None,
            'name': 'New Test',
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'parameters': {},
            'time_series': [],
            'results': [],
            'averages': {}
        }
        
        # Load last project if exists
        if self.settings['last_project']:
            project = self.db.load_project(self.settings['last_project'])
            if project:
                self.current_project = project
        
        # Setup UI
        self.setup_ui()
        self.setup_menu()
        self.apply_theme()
        self.show_page("DASHBOARD")
    
    def setup_ui(self):
        # Create stacked widget for pages
        self.stacked_widget = QStackedWidget()
        
        # Create pages
        self.dashboard_page = DashboardPage(self)
        self.parameters_page = ParametersPage(self)
        self.data_entry_page = DataEntryPage(self)
        self.results_page = ResultsPage(self)
        self.plots_page = PlotsPage(self)
        
        # Add pages to stack
        self.stacked_widget.addWidget(self.dashboard_page)
        self.stacked_widget.addWidget(self.parameters_page)
        self.stacked_widget.addWidget(self.data_entry_page)
        self.stacked_widget.addWidget(self.results_page)
        self.stacked_widget.addWidget(self.plots_page)
        
        # Set central widget
        self.setCentralWidget(self.stacked_widget)
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def setup_menu(self):
        # Create menu bar
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("File")
        
        new_action = QAction("New Test", self)
        new_action.triggered.connect(self.create_new_test)
        file_menu.addAction(new_action)
        
        open_action = QAction("Open Test...", self)
        open_action.triggered.connect(self.open_project_dialog)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save Test", self)
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save Test As...", self)
        save_as_action.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("Export Report...", self)
        export_action.triggered.connect(self.export_report)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menu_bar.addMenu("Edit")
        
        # View menu
        view_menu = menu_bar.addMenu("View")
        view_menu.addAction("Dashboard", lambda: self.show_page("DASHBOARD"))
        view_menu.addAction("Parameters", lambda: self.show_page("PARAMETERS"))
        view_menu.addAction("Data Entry", lambda: self.show_page("DATA_ENTRY"))
        view_menu.addAction("Results", lambda: self.show_page("RESULTS"))
        view_menu.addAction("Plots", lambda: self.show_page("PLOTS"))
        
        # Language menu
        lang_menu = menu_bar.addMenu("Language")
        
        english_action = QAction("English", self)
        english_action.triggered.connect(lambda: self.set_language("en"))
        lang_menu.addAction(english_action)
        
        french_action = QAction("French", self)
        french_action.triggered.connect(lambda: self.set_language("fr"))
        lang_menu.addAction(french_action)
        
        # Theme menu
        theme_menu = menu_bar.addMenu("Theme")
        
        dark_action = QAction("Dark", self)
        dark_action.triggered.connect(lambda: self.set_theme("dark"))
        theme_menu.addAction(dark_action)
        
        light_action = QAction("Light", self)
        light_action.triggered.connect(lambda: self.set_theme("light"))
        theme_menu.addAction(light_action)
        
        # Help menu
        help_menu = menu_bar.addMenu("Help")
        
        tutorial_action = QAction("Tutorials", self)
        tutorial_action.triggered.connect(self.show_tutorials)
        help_menu.addAction(tutorial_action)
        
        about_action = QAction("About RamWare", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def apply_theme(self):
        """Apply the current theme settings"""
        if self.settings['theme'] == 'dark':
            self.apply_dark_theme()
        else:
            self.apply_light_theme()
    
    def apply_dark_theme(self):
        """Apply dark theme to the application"""
        dark_palette = QPalette()
        
        # Base colors
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(35, 35, 35))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Highlight, QColor(142, 45, 197).lighter())
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        
        # Disabled colors
        dark_palette.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
        dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
        
        self.setPalette(dark_palette)
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 1ex;
                font-weight: bold;
                color: #ddd;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                background-color: transparent;
                color: #ddd;
            }
        """)
    
    def apply_light_theme(self):
        """Apply light theme to the application"""
        light_palette = QPalette()
        
        # Base colors
        light_palette.setColor(QPalette.Window, QColor(240, 240, 240))
        light_palette.setColor(QPalette.WindowText, Qt.black)
        light_palette.setColor(QPalette.Base, Qt.white)
        light_palette.setColor(QPalette.AlternateBase, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ToolTipBase, Qt.white)
        light_palette.setColor(QPalette.ToolTipText, Qt.black)
        light_palette.setColor(QPalette.Text, Qt.black)
        light_palette.setColor(QPalette.Button, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ButtonText, Qt.black)
        light_palette.setColor(QPalette.BrightText, Qt.red)
        light_palette.setColor(QPalette.Highlight, QColor(66, 134, 244))
        light_palette.setColor(QPalette.HighlightedText, Qt.white)
        
        self.setPalette(light_palette)
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 1ex;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                background-color: transparent;
            }
        """)
    
    def show_page(self, page_name):
        page_map = {
            "DASHBOARD": 0,
            "PARAMETERS": 1,
            "DATA_ENTRY": 2,
            "RESULTS": 3,
            "PLOTS": 4
        }
        
        self.stacked_widget.setCurrentIndex(page_map[page_name])
        
        # Page-specific setup
        if page_name == "DASHBOARD":
            self.dashboard_page.load_recent_projects()
        elif page_name == "DATA_ENTRY":
            self.data_entry_page.setup_table()
        elif page_name == "RESULTS":
            self.results_page.display_results()
        elif page_name == "PLOTS":
            self.plots_page.update_plot()
    
    def create_new_test(self):
        self.current_project = {
            'id': None,
            'name': 'New Test',
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'parameters': {},
            'time_series': [],
            'results': [],
            'averages': {}
        }
        self.show_page("PARAMETERS")
    
    def open_project_dialog(self):
        projects = self.db.list_projects()
        if not projects:
            QMessageBox.information(self, "No Projects", "No saved projects found.")
            return
        
        # Create dialog to select project
        # (In a full implementation, this would be a proper dialog with project list)
        project_id, ok = QInputDialog.getItem(
            self, "Open Project", "Select a project:",
            [f"{p[1]} ({p[3][:10]})" for p in projects], 0, False
        )
        
        if ok and project_id:
            index = [f"{p[1]} ({p[3][:10]})" for p in projects].index(project_id)
            self.load_project(projects[index][0])
    
    def load_project(self, project_id):
        project = self.db.load_project(project_id)
        if project:
            self.current_project = project
            self.settings['last_project'] = project_id
            self.db.save_settings(self.settings)
            
            if self.current_project.get('parameters'):
                self.show_page("DATA_ENTRY")
            else:
                self.show_page("PARAMETERS")
    
    def save_project(self):
        if not self.current_project.get('name'):
            self.save_project_as()
            return
        
        project = self.db.save_project(self.current_project)
        if project:
            self.current_project = project
            self.settings['last_project'] = project['id']
            self.db.save_settings(self.settings)
            self.statusBar().showMessage(f"Project saved: {project['name']}")
            return True
        return False
    
    def save_project_as(self):
        name, ok = QInputDialog.getText(
            self, "Save Project", "Enter project name:",
            text=self.current_project.get('name', 'New Test')
        )
        
        if ok and name:
            self.current_project['name'] = name
            return self.save_project()
        return False
    
    def perform_calculations(self):
        """Perform all calculations for the current project"""
        params = self.current_project["parameters"]
        time_series = self.current_project["time_series"]
        results = []
        
        # Initialize values
        prev_meter_oil = 0.0
        prev_meter_water = 0.0
        prev_meter_liquid = 0.0
        
        # Process each time entry
        for i, entry in enumerate(time_series):
            result = {"Time": entry["Time"]}
            
            # Calculate volume differences
            if params["separation_type"] == "THREE PHASES":
                meter_oil = entry.get("Meter Oil (BBL)", 0)
                meter_water = entry.get("Meter Water (BBL)", 0)
                vs_oil = meter_oil - prev_meter_oil
                vs_water = meter_water - prev_meter_water
                wio = entry.get("WIO (%)", 0) / 100.0
                prev_meter_oil = meter_oil
                prev_meter_water = meter_water
            else:
                meter_liquid = entry.get("Meter Liquid (BBL)", 0)
                vs_liquid = meter_liquid - prev_meter_liquid
                bsw = entry.get("BSW (%)", 0) / 100.0
                prev_meter_liquid = meter_liquid
            
            # Calculate VCF and oil api 60f
            sep_temp = entry.get("Oil T (°C)", 0)  # Using oil temp as separator temp
            
            oil_api_60f = WellTestCalculator.calculate_oil_api_60f(
                params["oil_temp"], params["oil_api"]
            )
            
            vcf_sep = WellTestCalculator.calculate_vcf_sep(
                sep_temp, oil_api_60f
            )
            
            # Calculate GOR2 and shrinkage factor
            sep_p = entry.get("SEP P (PSIG)", 0)
            gor2 = WellTestCalculator.calculate_gor2(
                oil_api_60f, params["sg_gas"], 
                sep_p, sep_temp, params["gor2_method"]
            )
            
            sf = WellTestCalculator.calculate_shrinkage_factor(
                gor2, sep_p, oil_api_60f
            )
            
            # Calculate flow rates
            if params["separation_type"] == "THREE PHASES":
                q_oil, q_water = WellTestCalculator.calculate_three_phase_flow(
                    vs_oil, vs_water, wio, 
                    params["meter_factor"], sf, vcf_sep
                )
            else:
                q_oil, q_water = WellTestCalculator.calculate_two_phase_flow(
                    vs_liquid, bsw, 
                    params["meter_factor"], sf, vcf_sep
                )
            
            result["Q Oil"] = q_oil
            result["Q Water"] = q_water
            result["Total Q"] = q_oil + q_water
            
            # Calculate gas flow
            gas_t = entry.get("GAS T (°C)", 0)
            q_gas = WellTestCalculator.calculate_gas_flow(
                entry["GAS DP (inH₂O)"], sep_p, 
                gas_t, params["sg_gas"], 
                params["orifice_diameter"], params["line_bore"], 
                params["h2s"], params["co2"]
            )
            
            result["Q Gas"] = q_gas
            
            # Calculate GORs
            result["GOR1"] = (q_gas * 1000) / q_oil if q_oil > 0 else 0
            result["GOR2"] = gor2
            result["Total GOR"] = result["GOR1"] + gor2
            
            # Gas Lift specific calculations
            if params["production_type"] == "GAS LIFT":
                q_gas_inj = entry.get("Q Gas Inj (MSCF/D)", 0)
                result["Q Gas Inj"] = q_gas_inj
                
                formation_gas, gor1_formation, total_gor_formation = WellTestCalculator.calculate_for_gas_lift(
                    q_gas, q_gas_inj, q_oil, gor2
                )
                
                result["Formation Gas"] = formation_gas
                result["GOR1 Formation"] = gor1_formation
                result["Total GOR Formation"] = total_gor_formation
            
            results.append(result)
        
        self.current_project["results"] = results
        self.calculate_averages()
    
    def calculate_averages(self):
        """Calculate average values for all results"""
        results = self.current_project["results"]
        if not results:
            return
        
        averages = {}
        for key in results[0].keys():
            if key != "Time":
                values = [r[key] for r in results]
                averages[key] = sum(values) / len(values)
        
        self.current_project["averages"] = averages
    
    def export_report(self):
        """Export the current report to PDF"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Report", "", "PDF Files (*.pdf)"
        )
        
        if file_path:
            try:
                self.generate_pdf_report(file_path)
                self.statusBar().showMessage(f"Report exported to {file_path}")
                QMessageBox.information(self, "Export Successful", "PDF report generated successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to generate report: {str(e)}")
    
    def generate_pdf_report(self, file_path):
        """Generate PDF report using ReportLab"""
        # Create PDF document
        doc = SimpleDocTemplate(file_path, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title style
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Title'],
            fontSize=18,
            spaceAfter=12,
            alignment=1  # Center aligned
        )
        
        # Add title
        title = Paragraph("RamWare - Well Test Report", title_style)
        elements.append(title)
        
        # Add well information
        well_info = [
            ["Field:", self.current_project["parameters"].get("field_name", "")],
            ["Well:", self.current_project["parameters"].get("well_name", "")],
            ["Test Date:", self.current_project["parameters"].get("test_date", "")]
        ]
        well_table = Table(well_info, colWidths=[100, 300])
        well_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(well_table)
        elements.append(Spacer(1, 12))
        
        # Add summary table
        summary_data = [["Parameter", "Value", "Units"]]
        averages = self.current_project["averages"]
        
        # Add key metrics
        summary_data.append(["Q Oil", f"{averages.get('Q Oil', 0):.2f}", "BBL/D"])
        summary_data.append(["Q Water", f"{averages.get('Q Water', 0):.2f}", "BBL/D"])
        summary_data.append(["Total Liquid", f"{averages.get('Total Q', 0):.2f}", "BBL/D"])
        summary_data.append(["Q Gas", f"{averages.get('Q Gas', 0):.2f}", "MSCF/D"])
        summary_data.append(["GOR1", f"{averages.get('GOR1', 0):.2f}", "SCF/STB"])
        summary_data.append(["Total GOR", f"{averages.get('Total GOR', 0):.2f}", "SCF/STB"])
        
        if self.current_project["parameters"]["production_type"] == "GAS LIFT":
            summary_data.append(["Q Gas Inj", f"{averages.get('Q Gas Inj', 0):.2f}", "MSCF/D"])
            summary_data.append(["Formation Gas", f"{averages.get('Formation Gas', 0):.2f}", "MSCF/D"])
            summary_data.append(["GOR1 Formation", f"{averages.get('GOR1 Formation', 0):.1f}", "SCF/STB"])
        
        summary_data.append(["GOR2", f"{averages.get('GOR2', 0):.1f}", "SCF/STB"])
        
        if self.current_project["parameters"]["production_type"] == "GAS LIFT":
            summary_data.append(["Total GOR Formation", f"{averages.get('Total GOR Formation', 0):.1f}", "SCF/STB"])
        else:
            summary_data.append(["Total GOR", f"{averages.get('Total GOR', 0):.1f}", "SCF/STB"])
        
        summary_table = Table(summary_data, colWidths=[150, 100, 80])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8f8f8")),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 24))
        
        # Add footer
        footer = Paragraph(
            f"Report generated by {APP_NAME} v{VERSION} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            styles['Italic']
        )
        elements.append(footer)
        
        # Build PDF
        doc.build(elements)
    
    def set_language(self, language):
        """Set application language"""
        self.settings['language'] = language
        self.db.save_settings(self.settings)
        # In a full implementation, we would reload the UI with translations
        self.statusBar().showMessage(f"Language set to {language.upper()}")
    
    def set_theme(self, theme):
        """Set application theme"""
        self.settings['theme'] = theme
        self.db.save_settings(self.settings)
        self.apply_theme()
        self.statusBar().showMessage(f"Theme set to {theme}")
    
    def show_tutorials(self):
        """Show tutorials dialog"""
        # In a full implementation, this would show actual tutorials
        QMessageBox.information(self, "Tutorials", "Tutorials content will be shown here.")
    
    def show_about(self):
        """Show about dialog"""
        about_text = (
            f"<b>{APP_NAME} - Well Testing Software</b><br><br>"
            f"Version: {VERSION}<br>"
            f"Developed by: {AUTHOR}<br>"
            f"Company: {COMPANY}<br><br>"
            f"© {datetime.now().year} {COMPANY}. All rights reserved.<br><br>"
            f"Contact: {SUPPORT_EMAIL}"
        )
        QMessageBox.about(self, f"About {APP_NAME}", about_text)
    
    def closeEvent(self, event):
        # ... (rest of the method code remains unchanged)
        event.accept()

# =====================
# APPLICATION STARTUP
# =====================
if __name__ == "__main__":
    # Create application
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    
    # Create and show main window
    window = RamWareApp()
    window.show()
    
    # Run application
    sys.exit(app.exec())
def setup_ui(self):
    # Main layout
    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(50, 30, 50, 30)
    main_layout.setSpacing(30)
    
    # Header (Logo only, no text title)
    header_layout = QHBoxLayout()
    logo = QLabel()
    pixmap = QPixmap(":/icons/logo.png")
    if pixmap.isNull():
        pixmap = QPixmap("logo.png")  # fallback if resource path fails
    pixmap = pixmap.scaledToHeight(120, Qt.SmoothTransformation)
    logo.setPixmap(pixmap)
    logo.setAlignment(Qt.AlignCenter)
    header_layout.addWidget(logo, alignment=Qt.AlignCenter)
    
    # Remove the old title QLabel line:
    # title = QLabel("RamWare - Well Testing Software")
    # title.setStyleSheet("font-size: 38px; font-weight: bold; color: #ffffff;")
    # header_layout.addWidget(title, alignment=Qt.AlignCenter)
    
    # Buttons
    button_layout = QVBoxLayout()
    button_layout.setSpacing(20)
    button_layout.setContentsMargins(100, 0, 100, 0)
    
    self.new_test_btn = GradientButton("Create New Test")
    self.new_test_btn.setGradient(QColor("#2ecc71"), QColor("#27ae60"))
    self.new_test_btn.clicked.connect(self.parent.create_new_test)
    
    self.open_test_btn = GradientButton("Open Existing Test")
    self.open_test_btn.setGradient(QColor("#3498db"), QColor("#2980b9"))
    self.open_test_btn.clicked.connect(self.parent.open_project_dialog)
    
    self.tutorials_btn = GradientButton("Tutorials")
    self.tutorials_btn.setGradient(QColor("#9b59b6"), QColor("#8e44ad"))
    self.tutorials_btn.clicked.connect(self.parent.show_tutorials)
    
    button_layout.addWidget(self.new_test_btn)
    button_layout.addWidget(self.open_test_btn)
    button_layout.addWidget(self.tutorials_btn)
    
    # Recent projects
    recent_group = QGroupBox("Recent Projects")
    recent_layout = QVBoxLayout()
    
    self.recent_list = QComboBox()
    self.recent_list.setMinimumHeight(35)
    recent_layout.addWidget(self.recent_list)
    
    open_recent_btn = GradientButton("Open Selected Project")
    open_recent_btn.setGradient(QColor("#f39c12"), QColor("#d35400"))
    open_recent_btn.clicked.connect(self.open_recent_project)
    recent_layout.addWidget(open_recent_btn)
    
    recent_group.setLayout(recent_layout)
    
    # Footer
    footer = QLabel(f"© {datetime.now().year} {COMPANY} | Version {VERSION}")
    footer.setStyleSheet("color: #7f8c8d; font-size: 12px;")
    footer.setAlignment(Qt.AlignCenter)
    
    # Add to main layout
    main_layout.addLayout(header_layout)
    main_layout.addStretch(1)
    main_layout.addLayout(button_layout)
    main_layout.addStretch(1)
    main_layout.addWidget(recent_group)
    main_layout.addStretch(1)
    main_layout.addWidget(footer)
    
    self.setLayout(main_layout)
def setup_ui(self):
    # Main layout
    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(50, 30, 50, 30)
    main_layout.setSpacing(30)
    
    # Header (Logo only, no text title)
    header_layout = QHBoxLayout()
    logo = QLabel()
    pixmap = QPixmap(":/icons/logo.png")
    if pixmap.isNull():
        pixmap = QPixmap("logo.png")  # fallback if resource path fails
    pixmap = pixmap.scaledToHeight(120, Qt.SmoothTransformation)
    logo.setPixmap(pixmap)
    logo.setAlignment(Qt.AlignCenter)
    header_layout.addWidget(logo, alignment=Qt.AlignCenter)
    
    # Remove the old title QLabel line:
    # title = QLabel("RamWare - Well Testing Software")
    # title.setStyleSheet("font-size: 38px; font-weight: bold; color: #ffffff;")
    # header_layout.addWidget(title, alignment=Qt.AlignCenter)
    
    # ... rest of your setup_ui code ...
