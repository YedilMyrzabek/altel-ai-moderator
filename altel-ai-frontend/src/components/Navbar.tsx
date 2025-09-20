import type {FC} from "react";
import { ChartPie, Youtube, BarChart3 } from "lucide-react";
import { Link } from "react-router-dom";

const Navbar: FC = () => {
  return (
    <nav className="bg-altel-pink text-white shadow-md">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <ChartPie className="w-6 h-6" />
          <span className="font-bold text-lg">Altel AI Moderator</span>
        </div>
        <div className="flex space-x-6">
          <Link to="/" className="hover:underline">Dashboard</Link>
          <Link to="/parser" className="hover:underline flex items-center space-x-1">
            <Youtube className="w-4 h-4" /> <span>Парсер</span>
          </Link>
          <Link to="/reports" className="hover:underline flex items-center space-x-1">
            <BarChart3 className="w-4 h-4" /> <span>Отчёты</span>
          </Link>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
