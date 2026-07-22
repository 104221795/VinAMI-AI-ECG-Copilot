"use client";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="vi">
      <body>
        <main className="vm-main">
          <div className="vm-state vm-state--error" role="alert">
            <h1>Ứng dụng không khả dụng</h1>
            <p>Không thể khởi động an toàn không gian làm việc nghiên cứu.</p>
            <button className="vm-button" onClick={reset}>
              Thử lại
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
