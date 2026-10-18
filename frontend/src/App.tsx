import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import MainPage from "./pages/MainPage";
import DocumentDetails from "./pages/DocumentDetails";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainPage />} />
        <Route path="/documents/:id" element={<DocumentDetails />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}