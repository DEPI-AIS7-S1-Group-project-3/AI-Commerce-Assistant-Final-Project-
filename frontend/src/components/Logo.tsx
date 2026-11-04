import { Link } from "react-router-dom";

export default function Logo() {
  return (
    <Link to="/" className="flex items-baseline gap-2" aria-label="دكان تك - الصفحة الرئيسية">
      <span className="font-display text-2xl font-bold leading-none text-ink">دكان تك</span>
      <span className="font-display text-sm font-bold uppercase leading-none text-green" dir="ltr">
        Dokkan Tech
      </span>
    </Link>
  );
}
