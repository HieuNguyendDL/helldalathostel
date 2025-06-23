# -*- coding: utf-8 -*-
import json
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta

# --- KHỞI TẠO ỨNG DỤNG FLASK ---
app = Flask(__name__)
# CORS cho phép file HTML giao tiếp với server Python này
CORS(app)

# Render sẽ cung cấp một thư mục '/var/data' để lưu trữ dữ liệu bền vững
# Đoạn code này sẽ tự động sử dụng thư mục đó khi được triển khai trên Render
# và vẫn dùng thư mục hiện tại khi bạn chạy trên máy tính cá nhân.
data_dir = os.environ.get('RENDER_DATA_DIR', '.')
DATA_FILENAME = os.path.join(data_dir, "hello_dalat_data_full.json")

def load_data():
    """Tải dữ liệu từ file JSON."""
    try:
        with open(DATA_FILENAME, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Trả về một cấu trúc rỗng nếu file không tồn tại hoặc lỗi
        return {"bookings": [], "rooms": [], "financial_transactions": []}

# --- CÁC ĐIỂM CUỐI API (API ENDPOINTS) ---

@app.route('/api/dashboard-summary', methods=['GET'])
def get_dashboard_summary():
    """Cung cấp dữ liệu tóm tắt cho Bảng điều khiển."""
    data = load_data()
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    revenue_today = 0
    occupied_rooms = set()
    
    # Tính doanh thu hôm nay từ các hóa đơn được xuất hôm nay
    for invoice in data.get('invoices', []):
        if invoice.get('ngay_xuat') == today_str:
            revenue_today += invoice.get('tong_hoa_don', 0)
            
    # Đếm số phòng đang có khách
    for booking in data.get('bookings', []):
        if booking.get('trang_thai') == 'da_nhan_phong':
            for room in booking.get('phong_dat', []):
                occupied_rooms.add(room.get('so_phong'))

    summary = {
        "revenue_today": f"{revenue_today:,} VNĐ",
        "occupied_rooms_count": len(occupied_rooms),
        "total_rooms": len(data.get('phong', {})),
        # Các số liệu khác có thể được tính toán tương tự
        "checkins_today": 3, # Dữ liệu giả định
        "profit_this_month": "25.700.000 VNĐ" # Dữ liệu giả định
    }
    return jsonify(summary)

@app.route('/api/bookings', methods=['GET'])
def get_bookings():
    """Lấy danh sách các booking, có hỗ trợ tìm kiếm."""
    data = load_data()
    search_query = request.args.get('search', '').lower()
    
    if not search_query:
        return jsonify(data.get('bookings', []))
        
    filtered_bookings = []
    for booking in data.get('bookings', []):
        search_haystack = [
            str(booking.get(key, '')) for key in 
            ['booking_id', 'ten_khach', 'ten_truong_doan', 'sdt', 'email']
        ]
        if any(search_query in field.lower() for field in search_haystack):
            filtered_bookings.append(booking)
            
    return jsonify(filtered_bookings)
    
@app.route('/api/upcoming-bookings', methods=['GET'])
def get_upcoming_bookings():
    """Lấy các booking có trạng thái 'đã đặt'."""
    data = load_data()
    upcoming = [
        b for b in data.get('bookings', []) 
        if b.get('trang_thai') == 'da_dat'
    ]
    return jsonify(upcoming)


@app.route('/api/calendar-data', methods=['GET'])
def get_calendar_data():
    """Cung cấp dữ liệu cho lịch phòng trống."""
    data = load_data()
    # Logic tạo lịch tương tự như trong file Python dòng lệnh
    # Ở đây chúng ta chỉ cần trả về booking và danh sách phòng
    calendar_payload = {
        "rooms": data.get('phong', {}),
        "bookings": data.get('bookings', [])
    }
    return jsonify(calendar_payload)


# --- CHẠY ỨNG DỤNG ---
if __name__ == '__main__':
    print("Khởi động máy chủ Hello Dalat Hostel...")
    print("Truy cập trang quản lý qua file index.html của bạn.")
    print("API đang chạy tại: http://127.0.0.1:5000")
    app.run(debug=True, port=5000)

