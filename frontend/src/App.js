import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Workspace from "@/pages/Workspace";
import DrainLayoutPage from "@/pages/DrainLayoutPage";
import SupplyPage from "@/pages/SupplyPage";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Workspace />} />
          <Route path="/drain/:pid" element={<DrainLayoutPage />} />
          <Route path="/suppliers/:pid" element={<SupplyPage />} />
        </Routes>
      </BrowserRouter>
      <Toaster theme="dark" position="bottom-right" richColors />
    </div>
  );
}

export default App;
