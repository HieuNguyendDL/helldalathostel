# -*- coding: utf-8 -*-
import json
import os
import io
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from datetime import datetime, timedelta
from collections import defaultdict

# --- RENDER DEPLOYMENT SETUP ---
data_dir = os.environ.get('RENDER_DATA_DIR', '.')
DATA_FILENAME = os.path.join(data_dir, "hello_dalat_data_full.json")

# --- LIBRARY CHECK ---
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_INSTALLED = True
except ImportError:
    REPORTLAB_INSTALLED = False

# --- CONSTANTS ---
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
FONT_FILE = "DejaVuSans.ttf"

# --- CORE SYSTEM CLASS ---
class HostelBookingSystem:
    def __init__(self, filename):
        self.filename = filename
        self.data = {}
        self._load_data()
        self._register_font()

    def _register_font(self):
        if REPORTLAB_INSTALLED and os.path.exists(FONT_FILE):
            pdfmetrics.registerFont(TTFont('DejaVu', FONT_FILE))
            pdfmetrics.registerFontFamily('DejaVu', normal='DejaVu', bold='DejaVu', italic='DejaVu', boldItalic='DejaVu')

    def _load_data(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            else:
                self.data = self._get_default_structure()
                self._save_data()
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading data file, using default structure. Error: {e}")
            self.data = self._get_default_structure()
        self._ensure_data_integrity()

    def _save_data(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"CRITICAL: Could not save data to {self.filename}. Error: {e}")

    def _get_default_structure(self):
        return {"info": { "ten_hostel": "Hello Dalat Hostel", "dia_chi": "33/18/2 Phan Đình Phùng, P.1, Đà Lạt", "so_dien_thoai": "0969975935" }, "phong": { "101": {"loai_phong": "Family Room", "gia_goc": 450000}, "201": {"loai_phong": "Deluxe Queen Room", "gia_goc": 400000}, "102": {"loai_phong": "Single Room", "gia_goc": 180000}, "202": {"loai_phong": "Single Room", "gia_goc": 180000}, "301": {"loai_phong": "Standard Double Room", "gia_goc": 250000}, "302": {"loai_phong": "Standard Double Room", "gia_goc": 250000}, "103": {"loai_phong": "Deluxe Double Room", "gia_goc": 300000}, "203": {"loai_phong": "Deluxe Double Room", "gia_goc": 300000} }, "danh_muc_dich_vu": [ {"id": "S1", "ten": "Nước suối", "don_vi": "chai", "gia": 10000}, {"id": "S2", "ten": "Giặt ủi", "don_vi": "kg", "gia": 30000} ], "bookings": [], "invoices": [], "financial_transactions": [], "counters": { "booking_le": 0, "booking_doan": 0, "dich_vu": 2, "invoice": 0, "transaction": 0 } }
    
    def _ensure_data_integrity(self):
        for key, default_value in [('bookings', []), ('invoices', []), ('financial_transactions', []), ('counters', {})]:
            self.data.setdefault(key, default_value)
        for key, default_value in [('booking_le', 0), ('booking_doan', 0), ('dich_vu', 0), ('invoice', 0), ('transaction', 0)]:
            self.data['counters'].setdefault(key, default_value)
        for booking in self.data.get('bookings', []):
            booking.setdefault('thanh_toan', [])
            booking.setdefault('dich_vu_da_dung', [])
    
    def _generate_id(self, counter_key, prefix):
        self.data['counters'][counter_key] = self.data['counters'].get(counter_key, 0) + 1
        return f"{prefix}{self.data['counters'][counter_key]}"

    def _calculate_room_cost(self, booking):
        try:
            nights = (datetime.strptime(booking['check_out_date'], DATE_FORMAT) - datetime.strptime(booking['check_in_date'], DATE_FORMAT)).days
            nights = max(1, nights)
            total_cost = sum(p.get('gia_thoa_thuan', 0) * nights for p in booking.get('phong_dat', []))
            return nights, total_cost
        except (ValueError, TypeError): return 0, 0

    def _calculate_service_cost(self, booking):
        return sum(s.get('gia', 0) * s.get('so_luong', 0) for s in booking.get('dich_vu_da_dung', []))

    def _log_transaction(self, trans_type, amount, method, description, details):
        trans_id = self._generate_id('transaction', "GD-")
        transaction = {"transaction_id": trans_id, "type": trans_type, "date": datetime.now().strftime(DATETIME_FORMAT), "amount": amount, "method": method, "description": description, **details}
        self.data.setdefault('financial_transactions', []).append(transaction)

    def get_all_data(self): return self.data

    def find_booking_by_id(self, booking_id):
        for index, booking in enumerate(self.data.get('bookings', [])):
            if booking.get('booking_id') == booking_id: return booking, index
        return None, -1

    def create_booking(self, booking_data):
        loai_booking = booking_data.get('guest_type', 'le')
        booking_id = self._generate_id(f"booking_{loai_booking}", "B" if loai_booking == 'le' else "D")
        new_booking = {
            "booking_id": booking_id, "loai_booking": loai_booking,
            "ten_khach": booking_data.get('guest_name') if loai_booking == 'le' else None,
            "ten_truong_doan": booking_data.get('guest_name') if loai_booking == 'doan' else None,
            "sdt": booking_data.get('guest_phone'), "email": booking_data.get('guest_email'),
            "check_in_date": booking_data.get('checkin_date'), "check_out_date": booking_data.get('checkout_date'),
            "phong_dat": [], "dich_vu_da_dung": [], "thanh_toan": [], "trang_thai": "da_dat"
        }
        all_rooms_info = self.data.get('phong', {})
        for room in booking_data.get('rooms', []):
            room_info = all_rooms_info.get(room.get('room_id'), {})
            new_booking['phong_dat'].append({
                "so_phong": room.get('room_id'), "gia_thoa_thuan": room.get('price'),
                "loai_phong": room_info.get('loai_phong', 'Unknown')
            })
        self.data['bookings'].append(new_booking)
        self._save_data()
        return new_booking

    def update_booking_info(self, booking_id, update_data):
        booking, index = self.find_booking_by_id(booking_id)
        if booking:
            booking.update(update_data)
            self.data['bookings'][index] = booking
            self._save_data()
            return booking
        return None
        
    def delete_booking(self, booking_id):
        _, index = self.find_booking_by_id(booking_id)
        if index is not None and index > -1:
            del self.data['bookings'][index]
            self._save_data()
            return True
        return False

    def check_room_availability(self, start_date_str, end_date_str):
        start_date = datetime.strptime(start_date_str, DATE_FORMAT)
        end_date = datetime.strptime(end_date_str, DATE_FORMAT)
        booked_rooms = set()
        for b in self.data['bookings']:
             if b.get('trang_thai') == 'da_huy': continue
             booking_start = datetime.strptime(b['check_in_date'], DATE_FORMAT)
             booking_end = datetime.strptime(b['check_out_date'], DATE_FORMAT)
             if start_date < booking_end and booking_start < end_date:
                 for p in b.get('phong_dat', []): booked_rooms.add(p.get('so_phong'))
        return sorted(list(set(self.data['phong'].keys()) - booked_rooms))

    def change_booking_status(self, booking_id, new_status):
        booking, index = self.find_booking_by_id(booking_id)
        if booking:
            booking['trang_thai'] = new_status
            if new_status == 'da_tra_phong':
                self.create_invoice(booking)
            self._save_data()
            return booking
        return None

    def create_invoice(self, booking):
        _, total_room_cost = self._calculate_room_cost(booking)
        total_service_cost = self._calculate_service_cost(booking)
        total_bill = total_room_cost + total_service_cost
        total_paid = sum(p['so_tien'] for p in booking.get('thanh_toan', []))
        
        self.data['invoices'] = [inv for inv in self.data.get('invoices', []) if inv.get('booking_id') != booking.get('booking_id')]
        
        invoice_id = self._generate_id('invoice', "HD-")
        invoice_data = {
            "invoice_id": invoice_id, "booking_id": booking['booking_id'], "ngay_xuat": datetime.now().strftime(DATE_FORMAT),
            "ten_khach_hang": booking.get('ten_khach') or booking.get('ten_truong_doan'),
            "tong_hoa_don": total_bill, "da_thanh_toan": total_paid
        }
        self.data['invoices'].append(invoice_data)
        
        self._log_transaction('thu', total_bill, 'tong_hop', f"Doanh thu từ Booking {booking['booking_id']}",
            {"source": "Doanh thu phòng/dịch vụ", "related_invoice_id": invoice_id})
        self._save_data()
        return invoice_data
        
    def generate_invoice_pdf_data(self, booking_id):
        if not REPORTLAB_INSTALLED: return None
        booking, _ = self.find_booking_by_id(booking_id)
        if not booking: return None
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setFont('DejaVu', 10)
        
        hostel_info = self.data['info']
        c.setFont('DejaVu', 14); c.drawString(inch, 10.5 * inch, hostel_info['ten_hostel'].upper())
        c.setFont('DejaVu', 10); c.drawString(inch, 10.25 * inch, f"Địa chỉ: {hostel_info['dia_chi']}")
        c.drawString(inch, 10.0 * inch, f"SĐT: {hostel_info['so_dien_thoai']}")
        
        invoice, _ = next(((inv, i) for i, inv in enumerate(self.data['invoices']) if inv.get('booking_id') == booking_id), (None, None))
        if not invoice: invoice = self.create_invoice(booking)
        
        c.setFont('DejaVu', 18); c.drawCentredString(4.25 * inch, 9.5 * inch, "HÓA ĐƠN THANH TOÁN")
        c.setFont('DejaVu', 10); c.drawString(5.5 * inch, 9.25 * inch, f"Số HĐ: {invoice['invoice_id']}")
        c.drawString(5.5 * inch, 9.1 * inch, f"Ngày xuất: {invoice['ngay_xuat']}")
        
        nights, _ = self._calculate_room_cost(booking)
        y = 8.7 * inch
        c.drawString(inch, y, "Khách hàng:"); c.drawString(2 * inch, y, invoice.get('ten_khach_hang', ''))
        y -= 0.25 * inch
        c.drawString(inch, y, "Mã Booking:"); c.drawString(2 * inch, y, booking_id)
        y -= 0.25 * inch
        c.drawString(inch, y, "Thời gian ở:"); c.drawString(2 * inch, y, f"{booking['check_in_date']} đến {booking['check_out_date']} ({nights} đêm)")

        y -= 0.5 * inch; c.setFont('DejaVu', 12)
        c.drawString(inch, y, "CHI TIẾT THANH TOÁN"); y -= 0.25 * inch; c.line(inch, y, 7.5 * inch, y); y -= 0.2 * inch
        
        c.setFont('DejaVu', 10); c.drawString(1.1 * inch, y, "Mô tả"); c.drawRightString(5.5 * inch, y, "Đơn giá");
        c.drawRightString(6.5 * inch, y, "Số lượng"); c.drawRightString(7.4 * inch, y, "Thành tiền")
        y -= 0.1 * inch
        
        for p in booking['phong_dat']:
            y -= 0.25 * inch; c.drawString(1.1 * inch, y, f"Tiền phòng {p.get('so_phong')} ({p.get('loai_phong')})")
            c.drawRightString(5.5 * inch, y, f"{p.get('gia_thoa_thuan', 0):,}"); c.drawRightString(6.5 * inch, y, f"{nights} đêm")
            c.drawRightString(7.4 * inch, y, f"{p.get('gia_thoa_thuan', 0) * nights:,} VNĐ")

        for s in booking['dich_vu_da_dung']:
            y -= 0.25 * inch; c.drawString(1.1 * inch, y, f"Dịch vụ: {s.get('ten')}")
            c.drawRightString(5.5 * inch, y, f"{s.get('gia', 0):,}"); c.drawRightString(6.5 * inch, y, f"{s.get('so_luong')} {s.get('don_vi')}")
            c.drawRightString(7.4 * inch, y, f"{s.get('gia', 0) * s.get('so_luong', 0):,} VNĐ")

        y -= 0.2 * inch; c.line(4.5*inch, y, 7.5*inch, y); y -= 0.25 * inch
        c.drawRightString(6.5 * inch, y, "Tổng cộng:"); c.drawRightString(7.4 * inch, y, f"{invoice['tong_hoa_don']:,} VNĐ")
        y -= 0.25 * inch
        c.drawRightString(6.5 * inch, y, "Đã thanh toán:"); c.drawRightString(7.4 * inch, y, f"{invoice['da_thanh_toan']:,} VNĐ")
        y -= 0.25 * inch; c.setFont('DejaVu', 12)
        c.drawRightString(6.5 * inch, y, "Còn lại:"); c.drawRightString(7.4 * inch, y, f"{invoice['tong_hoa_don'] - invoice['da_thanh_toan']:,} VNĐ")

        c.setFont('DejaVu', 10); c.drawCentredString(4.25 * inch, 1.5 * inch, "Cảm ơn quý khách và hẹn gặp lại!")
        
        c.save()
        buffer.seek(0)
        return buffer
        
    def add_payment_to_booking(self, booking_id, payment_data):
        booking, _ = self.find_booking_by_id(booking_id)
        if booking:
            booking['thanh_toan'].append({
                "so_tien": payment_data.get('amount'),
                "phuong_thuc": payment_data.get('method'),
                "ngay_thanh_toan": datetime.now().strftime(DATETIME_FORMAT),
                "ghi_chu": payment_data.get('note')
            })
            self._save_data()
            return booking
        return None

    def add_service_to_booking(self, booking_id, service_data):
        booking, _ = self.find_booking_by_id(booking_id)
        master_service = next((s for s in self.data['danh_muc_dich_vu'] if s['id'] == service_data.get('service_id')), None)
        if booking and master_service:
            booking['dich_vu_da_dung'].append({
                **master_service,
                "so_luong": service_data.get('quantity')
            })
            self._save_data()
            return booking
        return None

# --- KHỞI TẠO FLASK APP & SYSTEM ---
app = Flask(__name__)
CORS(app)
system = HostelBookingSystem(DATA_FILENAME)

# --- API ENDPOINTS ---
@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Hello Dalat Hostel API is running!"})

@app.route('/api/data', methods=['GET'])
def get_all_data():
    system._load_data()
    return jsonify(system.get_all_data())

@app.route('/api/bookings', methods=['POST'])
def add_booking():
    data = request.json
    try:
        return jsonify(system.create_booking(data)), 201
    except Exception as e: return jsonify({"error": str(e)}), 400

@app.route('/api/bookings/<string:booking_id>', methods=['GET'])
def get_booking(booking_id):
    booking, _ = system.find_booking_by_id(booking_id)
    if booking: return jsonify(booking)
    return jsonify({"error": "Booking not found"}), 404

@app.route('/api/bookings/<string:booking_id>', methods=['PUT'])
def update_booking_endpoint(booking_id):
    data = request.json
    updated = system.update_booking_info(booking_id, data)
    if updated: return jsonify(updated)
    return jsonify({"error": "Booking not found"}), 404

@app.route('/api/bookings/<string:booking_id>', methods=['DELETE'])
def delete_booking_endpoint(booking_id):
    if system.delete_booking(booking_id):
        return jsonify({"message": "Booking deleted successfully"}), 200
    return jsonify({"error": "Booking not found"}), 404

@app.route('/api/bookings/<string:booking_id>/status', methods=['PUT'])
def change_status_endpoint(booking_id):
    new_status = request.json.get('status')
    if not new_status: return jsonify({"error": "New status not provided"}), 400
    updated = system.change_booking_status(booking_id, new_status)
    if updated: return jsonify(updated)
    return jsonify({"error": "Booking not found"}), 404

@app.route('/api/available-rooms', methods=['GET'])
def get_available_rooms_endpoint():
    checkin, checkout = request.args.get('checkin'), request.args.get('checkout')
    if not all([checkin, checkout]): return jsonify({"error": "Missing date parameters"}), 400
    try:
        available_ids = system.check_room_availability(checkin, checkout)
        return jsonify({"available_rooms": available_ids, "all_rooms_info": system.data.get('phong', {})})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/bookings/<string:booking_id>/invoice-pdf', methods=['GET'])
def get_invoice_pdf(booking_id):
    pdf_buffer = system.generate_invoice_pdf_data(booking_id)
    if pdf_buffer:
        return send_file(pdf_buffer, as_attachment=True, download_name=f'Invoice_{booking_id}.pdf', mimetype='application/pdf')
    return jsonify({"error": "Could not generate PDF"}), 500

@app.route('/api/bookings/<string:booking_id>/payments', methods=['POST'])
def add_payment_endpoint(booking_id):
    data = request.json
    updated_booking = system.add_payment_to_booking(booking_id, data)
    if updated_booking:
        return jsonify(updated_booking), 200
    return jsonify({"error": "Booking not found"}), 404

@app.route('/api/bookings/<string:booking_id>/services', methods=['POST'])
def add_service_endpoint(booking_id):
    data = request.json
    updated_booking = system.add_service_to_booking(booking_id, data)
    if updated_booking:
        return jsonify(updated_booking), 200
    return jsonify({"error": "Booking or Service not found"}), 404

if __name__ == '__main__':
    print(f"Starting server...")
    print(f"Data file location: {os.path.abspath(DATA_FILENAME)}")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
