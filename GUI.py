import struct
import csv
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QListWidget,
    QSpinBox, QCheckBox, QComboBox, QTabWidget, QFrame, QGridLayout,
    QLineEdit, QGroupBox, QRadioButton, QSizePolicy, QScrollArea
)
from PySide6.QtCore import Qt, QSize, QMimeData
from PySide6.QtGui import QFont, QPalette, QColor, QDragEnterEvent, QDropEvent

def parse_datetime(hex_str1, hex_str2):
    """
    将两个形如 "YYMMDDhh"、"mmssxxxx"（只取前 4 位）的字符串解析为日期时间，
    并返回 (year, month, day, hour, minute, second, date_str, time_str)。
    """
    try:
        year_short = int(hex_str1[0:2])
        month = int(hex_str1[2:4])
        day = int(hex_str1[4:6])
        hour = int(hex_str1[6:8])
        minute = int(hex_str2[0:2])
        second = int(hex_str2[2:4])
    except ValueError:
        raise ValueError("无法解析时间：数据异常。")

    year = 2000 + year_short
    if not (1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError("无法解析时间：日期/时间字段不在有效范围内。")

    date_str = f"{year}/{month}/{day}"
    time_str = f"{hour:02d}:{minute:02d}:{second:02d}"
    return (year, month, day, hour, minute, second, date_str, time_str)

def parse_floats_left_low_right_high(hex_list):
    """
    将给定的十六进制字符串列表（每个元素形如 '0000A041'），
    解析为对应的浮点数列表（小端方式）。
    """
    floats = []
    for hx in hex_list:
        b = bytes.fromhex(hx)
        val = round(struct.unpack('<f', b)[0], 2)
        floats.append(val)
    return floats

def parse_bin_file(bin_filename, config):
    """
    针对单个 .bin 文件，读取并解析，返回一个“记录列表”。
    每条记录是 (year, month, day, hour, minute, second, date_str, time_str, float_values)。
    使用 config 字典来配置解析参数。
    """
    rows = []
    file_offset = config.get('file_offset', 0xC0)
    initial_block_size = config.get('initial_block_size', 132)
    subsequent_block_size = config.get('subsequent_block_size', 128)
    num_uint_initial = config.get('num_uint_initial', 33)
    num_uint_subsequent = config.get('num_uint_subsequent', 32)
    time_hex_indices = config.get('time_hex_indices', [0, 1])
    float_hex_start_index = config.get('float_hex_start_index', 2)
    group_size = config.get('group_size', 16)
    skip_first_group_item = config.get('skip_first_group_item', True)


    with open(bin_filename, 'rb') as f:
        f.seek(file_offset)
        first_read = True

        while True:
            if first_read:
                data = f.read(initial_block_size)
                if len(data) < initial_block_size:
                    break
                try:
                    unpacked = struct.unpack(f'>{num_uint_initial}I', data)
                except struct.error:
                    break
                values = unpacked[1:] if num_uint_initial > 0 else unpacked # 假设第一个值可能要跳过
                first_read = False
            else:
                data = f.read(subsequent_block_size)
                if len(data) < subsequent_block_size:
                    break
                try:
                    unpacked = struct.unpack(f'>{num_uint_subsequent}I', data)
                except struct.error:
                    break
                values = unpacked

            hex_values = [f"{val:08X}" for val in values]

            for i in range(0, len(hex_values), group_size):
                group = hex_values[i:i+group_size]
                if len(group) < group_size:
                    break
                if skip_first_group_item and len(group) > 0:
                    group = group[1:]  # 跳过第一个
                if len(group) < 2: # 至少要有时间数据
                    break

                try:
                    time_hex_1 = group[time_hex_indices[0]] if time_hex_indices[0] < len(group) else '00000000' # 默认值，防止索引错误
                    time_hex_2 = group[time_hex_indices[1]] if time_hex_indices[1] < len(group) else '00000000'
                    (
                        year, month, day, hour, minute, second,
                        date_str, time_str
                    ) = parse_datetime(time_hex_1, time_hex_2)
                except (ValueError, IndexError):
                    continue

                float_values_hex = group[float_hex_start_index:]
                float_values = parse_floats_left_low_right_high(float_values_hex)

                # 将解析后的记录暂存
                rows.append((year, month, day, hour, minute, second, date_str, time_str, float_values))

    return rows

def write_csv(csv_filename, rows, header_names, encoding='ANSI'):
    """
    将给定的记录列表，按时间排序后，去除重复时间戳并写出到指定的 csv 文件。
    使用用户自定义的 header_names 和编码格式。
    """
    # 按 (year, month, day, hour, minute, second) 排序
    rows.sort(key=lambda r: (r[0], r[1], r[2], r[3], r[4], r[5]))

    # =============== 去除重复时间戳 ===============
    unique_rows = []
    last_key = None
    for row in rows:
        # 以 (year, month, day, hour, minute, second) 作为唯一键
        current_key = (row[0], row[1], row[2], row[3], row[4], row[5])
        if current_key != last_key:
            unique_rows.append(row)
        last_key = current_key
    # ============================================

    with open(csv_filename, 'w', newline='', encoding=encoding) as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header_names) # 使用用户定义的表头

        for row in unique_rows:
            (year, month, day, hour, minute, second, date_str, time_str, float_values) = row
            # 交换最后两列(Val12, Val13) -- 如果原始逻辑有需要就保留
            if len(float_values) == 13:
                float_values[-2], float_values[-1] = float_values[-1], float_values[-2]
            writer.writerow([date_str, time_str] + float_values)

class BinParserApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BIN 解析工具")

        default_font = QFont("Segoe UI", 9) # Set default font here
        QApplication.setFont(default_font) # Apply to the entire application
        self.setFont(default_font) # Also set for the main window itself for consistency

        self.merge_var = False
        self.csv_encoding_var = "ANSI"

        default_header_names = [
            "日期", "时间",
            "压力设定/mbar", "实际压力/mbar",
            "设定温度/℃",  "实际温度/℃",
            "设定功率/KW", "实际功率/KW",
            "加热电阻/mΩ", "加热电压/V",
            "加热电流/A",  "毫托计/Pa",
            "氩气流量/SLM", "温升/℃/min",
            "氟利昂流量/SLM"
        ]

        self.config_params = {
            'file_offset': 0xC0,
            'initial_block_size': 132,
            'subsequent_block_size': 128,
            'num_uint_initial': 33,
            'num_uint_subsequent': 32,
            'time_hex_indices_str': "0,1",
            'float_hex_start_index': 2,
            'group_size': 16,
            'skip_first_group_item': True,
            'header_names': default_header_names[:], # Create a copy
            'csv_encoding': "ANSI" # Default encoding in config
        }

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.setup_ui()
        self.apply_modern_style() # Apply modern style after UI setup
        self.resize_window_to_4_3() # Resize window to 4:3 aspect ratio

    def resize_window_to_4_3(self):
        """设置窗口初始大小为 4:3 比例"""
        initial_width = 800  # 初始宽度，可以根据需要调整
        initial_height = int(initial_width * 3 / 4)
        self.resize(initial_width, initial_height)
        self.setMinimumSize(QSize(640, 480)) # 设置最小尺寸，防止窗口过小

    def apply_modern_style(self):
        # Basic flat style - you can customize colors further
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0; /* Light gray background */
            }
            QTabWidget::pane {
                background-color: #ffffff; /* White tab content background */
                border: 0;
            }
            QTabBar::tab {
                background-color: #e0e0e0; /* Light tab background */
                border: 0;
                padding: 8px 15px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff; /* Selected tab white background */
            }
            QPushButton {
                background-color: #dddddd; /* Light button background */
                border: 0;
                padding: 8px 15px;
                border-radius: 5px;
                font-size: 10pt; /* Slightly larger button font */
            }
            QPushButton:hover {
                background-color: #cccccc; /* Slightly darker on hover */
            }
            QLineEdit, QSpinBox, QComboBox, QListWidget {
                border: 1px solid #c0c0c0; /* Light border for input widgets */
                border-radius: 3px;
                padding: 5px;
                background-color: #ffffff;
                min-height: 28px; /* Increased min-height to prevent text clipping */
            }
            QLabel {
                font-size: 9pt; /* Ensure labels are readable */
            }
            QGroupBox {
                border: 1px solid #c0c0c0;
                border-radius: 5px;
                margin-top: 10px; /* Space for title */
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center; /* Position at the top center */
                padding: 0 5px;
                background-color: #f0f0f0; /* Match main background */
                font-weight: bold; /* Make group box titles bold */
            }
            QRadioButton {
                background-color: transparent; /* Radio button background transparent */
            }
            QListWidget {
                font-size: 9pt; /* List widget font */
            }
            QComboBox {
                font-size: 9pt;
            }
            QSpinBox {
                font-size: 9pt;
            }
            QLineEdit {
                font-size: 9pt;
            }
            QCheckBox {
                font-size: 9pt;
            }
        """)


    def setup_ui(self):
        # Middle Section: Notebook for File List, Config, Header and Other Config
        self.middle_section_notebook = QTabWidget()

        # Tab 1: File List
        file_list_tab = QWidget()
        self.middle_section_notebook.addTab(file_list_tab, "文件列表")
        file_list_layout = QVBoxLayout(file_list_tab)

        listbox_frame = QFrame()
        listbox_layout = QHBoxLayout(listbox_frame)
        file_list_layout.addWidget(listbox_frame)

        self.listbox_files = QListWidget()
        listbox_layout.addWidget(self.listbox_files)
        self.listbox_files.keyPressEvent = self.listbox_delete_selected # Override key press event
        self.listbox_files.setAcceptDrops(True) # Enable drag and drop for file list

        # Tab 2: Parsing Configuration
        config_tab = QWidget()
        self.middle_section_notebook.addTab(config_tab, "解析配置")
        config_layout = QVBoxLayout(config_tab)

        config_frame = QFrame()
        config_grid_layout = QGridLayout(config_frame) # 使用 GridLayout for config settings
        config_layout.addWidget(config_frame)
        config_grid_layout.setColumnStretch(0, 1) # 让第一列可以伸缩
        config_grid_layout.setColumnStretch(1, 1) # 让第二列可以伸缩
        config_grid_layout.setContentsMargins(15, 15, 15, 15) # 添加外边距
        config_grid_layout.setHorizontalSpacing(20) # 设置水平间距
        config_grid_layout.setVerticalSpacing(15)   # 设置垂直间距


        group_box_basic = QGroupBox("基本配置") # Group box for basic settings
        basic_grid = QGridLayout(group_box_basic)
        config_grid_layout.addWidget(group_box_basic, 0, 0, 1, 2) # 放置在第一行，跨两列
        basic_grid.setContentsMargins(10, 10, 10, 10) # GroupBox 内部边距
        basic_grid.setHorizontalSpacing(10)
        basic_grid.setVerticalSpacing(8)


        # Row 0: File Offset
        label_offset = QLabel("文件偏移地址 (Hex): 0x")
        self.entry_offset = QLineEdit(f'{self.config_params["file_offset"]:X}')
        self.entry_offset.editingFinished.connect(self.update_offset_config)
        basic_grid.addWidget(label_offset, 0, 0)
        basic_grid.addWidget(self.entry_offset, 0, 1)

        # Row 1: Initial Block Size
        label_initial_block = QLabel("初始块大小 (bytes):")
        self.spin_initial_block = QSpinBox()
        self.spin_initial_block.setRange(1, 2048)
        self.spin_initial_block.setValue(self.config_params['initial_block_size'])
        basic_grid.addWidget(label_initial_block, 1, 0)
        basic_grid.addWidget(self.spin_initial_block, 1, 1)

        # Row 2: Subsequent Block Size
        label_subsequent_block = QLabel("后续块大小 (bytes):")
        self.spin_subsequent_block = QSpinBox()
        self.spin_subsequent_block.setRange(1, 2048)
        self.spin_subsequent_block.setValue(self.config_params['subsequent_block_size'])
        basic_grid.addWidget(label_subsequent_block, 2, 0)
        basic_grid.addWidget(self.spin_subsequent_block, 2, 1)

        group_box_uint = QGroupBox("Uint 配置") # Group box for Uint settings
        uint_grid = QGridLayout(group_box_uint)
        config_grid_layout.addWidget(group_box_uint, 1, 0) # 放置在第二行，第一列
        uint_grid.setContentsMargins(10, 10, 10, 10) # GroupBox 内部边距
        uint_grid.setHorizontalSpacing(10)
        uint_grid.setVerticalSpacing(8)

        # Row 0: Initial Uint Count
        label_uint_initial = QLabel("初始块 uint 数量:")
        self.spin_uint_initial = QSpinBox()
        self.spin_uint_initial.setRange(0, 100)
        self.spin_uint_initial.setValue(self.config_params['num_uint_initial'])
        uint_grid.addWidget(label_uint_initial, 0, 0)
        uint_grid.addWidget(self.spin_uint_initial, 0, 1)

        # Row 1: Subsequent Uint Count
        label_uint_subsequent = QLabel("后续块 uint 数量:")
        self.spin_uint_subsequent = QSpinBox()
        self.spin_uint_subsequent.setRange(0, 100)
        self.spin_uint_subsequent.setValue(self.config_params['num_uint_subsequent'])
        uint_grid.addWidget(label_uint_subsequent, 1, 0)
        uint_grid.addWidget(self.spin_uint_subsequent, 1, 1)

        group_box_hex = QGroupBox("Hex/数据组 配置") # Group box for Hex and Group settings
        hex_grid = QGridLayout(group_box_hex)
        config_grid_layout.addWidget(group_box_hex, 1, 1) # 放置在第二行，第二列
        hex_grid.setContentsMargins(10, 10, 10, 10) # GroupBox 内部边距
        hex_grid.setHorizontalSpacing(10)
        hex_grid.setVerticalSpacing(8)

        # Row 0: Time Hex Indices
        label_time_indices = QLabel("时间 Hex 索引 (逗号):")
        self.entry_time_indices = QLineEdit(self.config_params['time_hex_indices_str'])
        hex_grid.addWidget(label_time_indices, 0, 0)
        hex_grid.addWidget(self.entry_time_indices, 0, 1)

        # Row 1: Float Hex Start Index
        label_float_start_index = QLabel("Float Hex 起始索引:")
        self.spin_float_start_index = QSpinBox()
        self.spin_float_start_index.setRange(0, 99)
        self.spin_float_start_index.setValue(self.config_params['float_hex_start_index'])
        hex_grid.addWidget(label_float_start_index, 1, 0)
        hex_grid.addWidget(self.spin_float_start_index, 1, 1)

        # Row 2: Group Size
        label_group_size = QLabel("数据组大小:")
        self.spin_group_size = QSpinBox()
        self.spin_group_size.setRange(1, 100)
        self.spin_group_size.setValue(self.config_params['group_size'])
        hex_grid.addWidget(label_group_size, 2, 0)
        hex_grid.addWidget(self.spin_group_size, 2, 1)

        # Row 3: Skip First Group Item
        self.check_skip_first = QCheckBox("跳过每组第一个数据")
        hex_grid.addWidget(self.check_skip_first, 3, 0, 1, 2) # 跨两列

        # Row 4: CSV Encoding (Moved to Parsing Config)
        encoding_frame = QFrame()
        encoding_layout = QHBoxLayout(encoding_frame)
        label_encoding = QLabel("CSV 编码:")
        encoding_layout.addWidget(label_encoding)
        self.combo_encoding = QComboBox()
        self.combo_encoding.addItems(["ANSI", "UTF-8"])
        self.combo_encoding.setCurrentText(self.config_params['csv_encoding']) # Use config default
        encoding_layout.addWidget(self.combo_encoding)
        config_grid_layout.addWidget(encoding_frame, 2, 0, 1, 2) # 放置在第三行，跨两列


        # Tab 3: CSV Header Configuration
        header_config_tab = QWidget()
        self.middle_section_notebook.addTab(header_config_tab, "CSV表头配置")
        header_config_layout = QVBoxLayout(header_config_tab)

        # 使用 QScrollArea 包裹 header_config_frame
        self.header_scroll_area = QScrollArea()
        self.header_scroll_area.setWidgetResizable(True) # 允许内部 widget 调整大小
        self.header_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded) # 需要时显示垂直滚动条
        self.header_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # 禁用水平滚动条

        self.header_config_frame = QFrame()
        self.header_config_v_layout = QVBoxLayout(self.header_config_frame) # Vertical layout for header frames
        self.header_scroll_area.setWidget(self.header_config_frame) # 设置 scroll area 的内部 widget

        header_config_layout.addWidget(self.header_scroll_area) # 将 scroll area 添加到 tab 布局中
        self.header_frames = []
        self.refresh_header_frames()

        header_btn_frame = QFrame()
        header_btn_layout = QHBoxLayout(header_btn_frame)
        header_config_layout.addWidget(header_btn_frame)

        btn_add_header = QPushButton("添加列")
        btn_add_header.clicked.connect(self.add_header_column)
        header_btn_layout.addWidget(btn_add_header)
        btn_remove_header = QPushButton("删除列")
        btn_remove_header.clicked.connect(self.remove_header_column)
        header_btn_layout.addWidget(btn_remove_header)


        # Tab 4: Other Parsing Config (Reserved) - Renamed and Replaced Output Settings Tab
        other_config_tab = QWidget()
        self.middle_section_notebook.addTab(other_config_tab, "其他配置") # Renamed Tab
        other_config_layout = QVBoxLayout(other_config_tab)
        other_config_label = QLabel("此处预留用于添加其他配置项。")
        other_config_label.setAlignment(Qt.AlignCenter)
        other_config_layout.addWidget(other_config_label)

        # Right Side Frame: Select Files Button, Output Mode, and Parse Button
        right_side_frame = QFrame()
        right_side_layout = QVBoxLayout(right_side_frame)

        btn_select = QPushButton("选择 .bin 文件")
        btn_select.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed) # Fixed size for button
        btn_select.clicked.connect(self.on_select_files)
        right_side_layout.addWidget(btn_select)

        output_mode_group = QGroupBox("输出模式")
        output_mode_layout = QVBoxLayout(output_mode_group) # Changed to QVBoxLayout
        self.r1_separate = QRadioButton("分别输出CSV")
        self.r1_separate.setChecked(True) # Default to "分别输出CSV"
        output_mode_layout.addWidget(self.r1_separate)
        self.r2_merge = QRadioButton("合并到一个CSV")
        output_mode_layout.addWidget(self.r2_merge)
        right_side_layout.addWidget(output_mode_group)

        btn_parse = QPushButton("开始解析")
        btn_parse.clicked.connect(self.on_parse)
        right_side_layout.addWidget(btn_parse) # Add Parse button to right side layout


        # Central Horizontal Layout to hold Notebook and Right Side Frame
        central_horizontal_frame = QFrame()
        central_horizontal_layout = QHBoxLayout(central_horizontal_frame)
        central_horizontal_layout.addWidget(self.middle_section_notebook)
        central_horizontal_layout.addWidget(right_side_frame)

        self.main_layout.addWidget(central_horizontal_frame)


    def refresh_header_frames(self):
        for frame in self.header_frames:
            frame.deleteLater() # PySide6 way to remove widgets from layout and destroy
        self.header_frames = []
        for i in range(len(self.config_params['header_names'])):
            header_frame = self.create_header_frame(self.header_config_frame, i, self.config_params['header_names'][i])
            self.header_frames.append(header_frame)

    def create_header_frame(self, parent, index, default_name):
        frame = QFrame(parent)
        frame_layout = QHBoxLayout(frame)
        label = QLabel(f"列 {index+1}:")
        frame_layout.addWidget(label)
        entry = QLineEdit(default_name)
        frame_layout.addWidget(entry)
        self.header_config_v_layout.addWidget(frame) # Add to vertical layout
        return frame

    def add_header_column(self):
        self.config_params['header_names'].append(f"列 {len(self.config_params['header_names']) + 1}")
        self.refresh_header_frames()

    def remove_header_column(self):
        if len(self.config_params['header_names']) > 2: # 至少保留两列 (日期, 时间)
            self.config_params['header_names'].pop()
            self.refresh_header_frames()
        else:
            QMessageBox.information(self, "提示", "至少需要保留两列表头 (日期, 时间)。")

    def on_parse(self):
        file_paths = [self.listbox_files.item(i).text() for i in range(self.listbox_files.count())]
        if not file_paths:
            QMessageBox.critical(self, "错误", "尚未选择任何 .bin 文件！")
            return

        merge_to_one = self.r2_merge.isChecked() # Get output mode from RadioButtons
        csv_encoding = self.combo_encoding.currentText()

        config = {}
        try:
            config['file_offset'] = int(self.entry_offset.text(), 16) if self.entry_offset.text() else 0
            config['initial_block_size'] = self.spin_initial_block.value()
            config['subsequent_block_size'] = self.spin_subsequent_block.value()
            config['num_uint_initial'] = self.spin_uint_initial.value()
            config['num_uint_subsequent'] = self.spin_uint_subsequent.value()
            config['csv_encoding'] = csv_encoding # Get encoding from combobox

            time_indices_str = self.entry_time_indices.text()
            config['time_hex_indices'] = [int(x.strip()) for x in time_indices_str.split(',') if x.strip()]
            if len(config['time_hex_indices']) != 2:
                raise ValueError("时间索引需要两个数字，用逗号分隔。")

            config['float_hex_start_index'] = self.spin_float_start_index.value()
            config['group_size'] = self.spin_group_size.value()
            config['skip_first_group_item'] = self.check_skip_first.isChecked()

            header_names = [frame.findChild(QLineEdit).text() for frame in self.header_frames]
            config['header_names'] = header_names

        except ValueError as e:
            QMessageBox.critical(self, "配置错误", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "配置错误", f"配置参数错误: {e}")
            return

        if merge_to_one:
            out_filename, _ = QFileDialog.getSaveFileName(
                self,
                "保存合并的 CSV 文件",
                "",
                "CSV文件 (*.csv);;所有文件 (*.*)"
            )
            if not out_filename:
                return

            merged_records = []
            for bin_path in file_paths:
                try:
                    recs = parse_bin_file(bin_path, config)
                    merged_records.extend(recs)
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"解析失败：{bin_path}\n{e}")
                    return

            try:
                write_csv(out_filename, merged_records, header_names, encoding=csv_encoding)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"写CSV失败：\n{e}")
                return

            QMessageBox.information(self, "完成", f"合并输出成功，已生成：\n{out_filename}")

        else:
            success_list = []
            for bin_path in file_paths:
                try:
                    recs = parse_bin_file(bin_path, config)
                    base, _ = os.path.splitext(bin_path)
                    csv_path = base + ".csv"
                    write_csv(csv_path, recs, header_names, encoding=csv_encoding)
                    success_list.append(csv_path)
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"解析失败：{bin_path}\n{e}")

            if success_list:
                msg = "处理完成！生成的CSV文件：\n" + "\n".join(success_list)
                QMessageBox.information(self, "完成", msg)

    def on_select_files(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter("BIN files (*.bin);;All files (*.*)")
        if file_dialog.exec():
            paths = file_dialog.selectedFiles()
            if paths:
                for p in paths:
                    self.listbox_files.addItem(p)

    def listbox_delete_selected(self, event):
        if event.key() == Qt.Key_Delete:
            selected_items = self.listbox_files.selectedItems()
            for item in selected_items:
                row = self.listbox_files.row(item)
                self.listbox_files.takeItem(row)

    def update_offset_config(self):
        text = self.entry_offset.text()
        try:
            int(text, 16) if text else 0
        except ValueError:
            QMessageBox.critical(self, "错误", "文件偏移地址必须是有效的十六进制数")
            self.entry_offset.setText(f'{self.config_params["file_offset"]:X}') # Reset to last valid value

    # Drag and Drop Events for QListWidget
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if os.path.isfile(file_path) and file_path.lower().endswith(".bin"):
                    self.listbox_files.addItem(file_path)
        else:
            super().dropEvent(event)


if __name__ == "__main__":
    app = QApplication([])
    window = BinParserApp()
    window.show()
    app.exec()