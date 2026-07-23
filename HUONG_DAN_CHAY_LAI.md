# Hướng Dẫn Chạy Lại VinAMI ACS Operating System

Tài liệu này dành cho mentor hoặc người clone project về để chạy thử demo.

VinAMI hiện là **research-use MVP** cho luồng xử lý bệnh nhân nghi ngờ ACS. Hệ thống không phải thiết bị y tế đã kiểm định, không tự chẩn đoán, không tự loại trừ AMI và không tự kích hoạt cath-lab.

## 1. Cần cài trước

- Git
- Docker Desktop
- PowerShell hoặc terminal trong VS Code

Khuyến nghị chạy bằng Docker vì hệ thống gồm nhiều phần:

- FastAPI backend
- Next.js frontend
- PostgreSQL
- Redis
- worker xử lý event/timer

## 2. Clone repo

```powershell
git clone https://github.com/104221795/VinAMI-AI-ECG-Copilot.git
cd VinAMI-AI-ECG-Copilot\vinami-acs
```

Nếu đã clone rồi:

```powershell
git pull
cd vinami-acs
```

## 3. Tạo file môi trường

```powershell
Copy-Item .env.example .env
```

Trên macOS/Linux:

```bash
cp .env.example .env
```

## 4. Chạy hệ thống

```powershell
docker compose up --build -d
```

Kiểm tra các service:

```powershell
docker compose ps
```

Cần thấy các service chính đang chạy:

- `api`
- `web`
- `postgres`
- `redis`
- `worker`

Nếu muốn kiểm tra trực tiếp database, dùng user `vinami`, không dùng `postgres`:

```powershell
docker compose exec postgres psql -U vinami -d vinami_acs -c "\dt"
```

## 5. Chạy migration

```powershell
docker compose exec api alembic upgrade head
```

Kiểm tra backend:

```text
http://localhost:8000/health
http://localhost:8000/ready
```

Nếu `/ready` trả về `ready` là database schema đã ổn.

## 6. Seed demo cases

Chạy lệnh này để tạo dữ liệu demo:

```powershell
docker compose exec api python -m scripts.seed_demo_happy_cases
```

Script này tạo dữ liệu qua API thật, không bypass backend. Vì vậy timeline, audit, workflow, task và event vẫn được ghi theo luồng hệ thống.

## 7. Mở UI

Mở trình duyệt:

```text
http://localhost:3000
```

Trang chính sẽ chuyển tới:

```text
http://localhost:3000/command-center
```

## 8. Demo case nên xem

### Case 1 - Luồng đầy đủ

Tìm patient reference:

```text
VINAMI-DEMO-HAPPY-001
```

Case này dùng để xem:

- Command Center
- Clinical Case Workspace
- Triage và vitals
- ECG Workspace
- ECG five-label AI mock output
- Physician ECG interpretation
- Troponin timeline
- Clinical Reasoning
- Physician Decision
- Workflow task
- Timeline
- Audit
- Outcome

Đây là case tốt nhất để mentor xem luồng end-to-end.

### Case 2 - Safety case thiếu outcome

Tìm patient reference:

```text
VINAMI-DEMO-MISSING-OUTCOME-001
```

Case này chứng minh:

- task hoàn tất không tự tạo outcome;
- workflow không thay thế kết luận lâm sàng;
- outcome vẫn missing cho tới khi bác sĩ ghi nhận;
- audit và timeline vẫn lưu lại hoạt động.

## 9. ECG path xem được không?

Có. Sau khi seed demo cases, mở case `VINAMI-DEMO-HAPPY-001`, sau đó vào tab ECG hoặc URL dạng:

```text
http://localhost:3000/cases/{case_id}/ecg
```

ECG path mặc định xem được:

- ECG 12 chuyển đạo mô phỏng;
- waveform preview;
- quality status;
- five-label ECG AI output qua mock provider;
- physician review;
- repeat ECG reminder;
- dynamic ECG comparison nếu có hai ECG studies.

Lưu ý: đây là demo ECG AI bằng mock/provider trình diễn, không phải chẩn đoán thật.

## 10. PTB-XL / Grad-CAM showcase

Code path cho PTB-XL, ConvNeXt và Grad-CAM đã có trong repo, nhưng artifact nặng không được push lên GitHub:

```text
PTBXL/
VinStroke_ECG_artifacts/
*.pt
*.pth
*.onnx
```

Nếu có folder artifact local, có thể seed ECG showcase bằng:

```powershell
docker compose exec api python -m scripts.seed_ptbxl_artifact_ecg_cases
```

Khi đó sẽ có các case dạng:

```text
PTBXL-R23A-VISIBLE-NORM-xxxxx
PTBXL-R23A-VISIBLE-MI-xxxxx
PTBXL-R23A-VISIBLE-STTC-xxxxx
PTBXL-R23A-VISIBLE-CD-xxxxx
PTBXL-R23A-VISIBLE-HYP-xxxxx
```

Path này dùng để xem:

- ECG showcase theo 5 label;
- model score;
- provenance;
- Grad-CAM hoặc explanation artifact nếu có;
- serial ECG comparison.

## 11. Xem log khi lỗi

Backend:

```powershell
docker compose logs -f api
```

Frontend:

```powershell
docker compose logs -f web
```

Worker:

```powershell
docker compose logs -f worker
```

Database:

```powershell
docker compose logs -f postgres
```

## 12. Chạy lại từ đầu nếu muốn reset dữ liệu

Lệnh này sẽ xóa volume database local:

```powershell
docker compose down -v
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed_demo_happy_cases
```

Chỉ dùng khi muốn reset demo hoàn toàn.

## 13. Tóm tắt cho người review

Sau khi chạy xong, mở:

```text
http://localhost:3000/command-center
```

Xem theo thứ tự:

1. Chọn `VINAMI-DEMO-HAPPY-001`
2. Mở Clinical Case Workspace
3. Mở ECG Workspace
4. Mở Troponin Workspace
5. Mở Clinical Reasoning
6. Mở Workflow
7. Mở Timeline
8. Mở Audit

Điểm cần nhớ: AI trong VinAMI chỉ hỗ trợ đọc và tổng hợp bằng chứng. Quyết định cuối cùng vẫn thuộc về bác sĩ.
