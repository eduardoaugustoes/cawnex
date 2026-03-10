import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./index.css";
import { Layout } from "@/components/Layout";
import { ProjectList } from "@/pages/ProjectList";
import { ProjectVision } from "@/pages/ProjectVision";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<ProjectList />} />
          <Route path="/projects/:id" element={<ProjectVision />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
