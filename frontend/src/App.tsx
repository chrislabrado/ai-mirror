import { Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Dashboard } from "@/pages/Dashboard";
import { ExportGuidePage } from "@/pages/ExportGuide";
import { FocusLensPage } from "@/pages/FocusLens";
import { HistoryPage } from "@/pages/History";
import { ConversationDetailPage } from "@/pages/ConversationDetail";
import { InsightsPage } from "@/pages/Insights";
import { ReportsListPage } from "@/pages/ReportsList";
import { ReportViewerPage } from "@/pages/ReportViewer";
import { KnowledgeGraphPage } from "@/pages/KnowledgeGraph";
import { QueriesPage } from "@/pages/Queries";
import { TrajectoriesPage } from "@/pages/Trajectories";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/history/:id" element={<ConversationDetailPage />} />
        <Route path="/insights" element={<InsightsPage />} />
        <Route path="/insights/reports" element={<ReportsListPage />} />
        <Route path="/insights/reports/:id" element={<ReportViewerPage />} />
        <Route path="/trajectories" element={<TrajectoriesPage />} />
        <Route path="/graph" element={<KnowledgeGraphPage />} />
        <Route path="/queries" element={<QueriesPage />} />
        <Route path="/focus-lens" element={<FocusLensPage />} />
        <Route path="/export-guide" element={<ExportGuidePage />} />
      </Route>
    </Routes>
  );
}
