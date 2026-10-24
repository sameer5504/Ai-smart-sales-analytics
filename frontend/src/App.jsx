import { Routes, Route } from "react-router-dom";

import HomePage from "./shared/pages/HomePage";
import RegisterPage from "./features/auth/pages/RegisterPage";
import LoginPage from "./features/auth/pages/LoginPage";
import ProfilePage from "./features/profile/pages/ProfilePage";
import UploadPage from "./features/upload/pages/UploadPage";

import MappingReviewPage from "./features/upload/pages/MappingReviewPage";
import ChatbotPage from "./features/chatbot/pages/ChatbotPage";
import DashboardPage from "./features/dashboard/pages/DashboardPage";
import MyFilesPage from "./features/files/pages/MyFilesPage";

import ProtectedRoute from "./shared/routes/protectedRoute/protectedRoute";
import AppLayout from "./shared/components/AppLayout/AppLayout";
import AuthLayout from "./shared/components/AuthLayout/AuthLayout";
import { DatasetProvider } from "./shared/context/DatasetContext";
import RequireDataset from "./shared/routes/requireDataset/requireDataset";

function App() {
    return (
        <Routes>
            <Route path="/" element={<HomePage />} />
            <Route element={<AuthLayout />}>
                <Route path="/register" element={<RegisterPage />} />
                <Route path="/login" element={<LoginPage />} />
            </Route>

            <Route
                element={
                    <ProtectedRoute>
                        <DatasetProvider>
                            <AppLayout />
                        </DatasetProvider>
                    </ProtectedRoute>
                }
            >
                <Route path="/upload" element={<UploadPage />} />
                <Route path="/mapping" element={<MappingReviewPage />} />
                <Route path="/profile" element={<ProfilePage />} />

                <Route element={<RequireDataset />}>
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/assistant" element={<ChatbotPage />} />
                    <Route path="/my-files" element={<MyFilesPage />} />
                </Route>
            </Route>
        </Routes>
    );
}

export default App;
