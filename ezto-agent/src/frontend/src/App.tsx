import { Routes, Route, Navigate } from "react-router-dom";
import HomePage from "./pages/HomePage";
import NewProjectPage from "./pages/NewProjectPage";
import WorkflowPage from "./pages/WorkflowPage";

export default function App() {
  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/new" element={<NewProjectPage />} />
        <Route path="/workflow/:id/*" element={<WorkflowPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
