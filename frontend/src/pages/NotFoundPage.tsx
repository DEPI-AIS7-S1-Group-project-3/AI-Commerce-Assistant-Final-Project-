import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <section className="mx-auto max-w-md space-y-4 py-20 text-center">
      <h1 className="text-4xl">الصفحة غير موجودة</h1>
      <p className="text-ink-soft">قد يكون الرابط غير صحيح أو أن الصفحة لم تُنشأ بعد.</p>
      <Link to="/" className="btn-dark">
        العودة إلى الرئيسية
      </Link>
    </section>
  );
}
