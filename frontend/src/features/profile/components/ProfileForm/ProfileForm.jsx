import { useNavigate } from "react-router-dom";
import { logout } from "../../../../shared/utils/logout";
import { useProfile } from "../../hooks/useProfile";
import "./ProfileForm.css";

function ProfileForm() {
    const navigate = useNavigate();

    const {
        username,
        userId,
        displayName,
        message,
        saveProfile,
        handleDisplayNameChange,
    } = useProfile();

    const handleLogout = async () => {
        const loggedOut = await logout();

        if (loggedOut) {
            navigate("/login");
        }
    };

    return (
        <div className="profile-container">
            <div className="profile-card">
                <h1>Profile</h1>

                <div className="profile-field">
                    <label>Username</label>
                    <p>{username}</p>
                </div>

                <div className="profile-field">
                    <label>User ID</label>
                    <p>{userId}</p>
                </div>

                <div className="profile-field">
                    <label>Display Name</label>

                    <input
                        type="text"
                        value={displayName}
                        onChange={(e) => handleDisplayNameChange(e.target.value)}
                        placeholder="Enter your display name"
                    />
                </div>

                <button className="save-btn" type="button" onClick={saveProfile}>
                    Save
                </button>

                <button
                    className="back-menu-btn"
                    type="button"
                    onClick={() => navigate("/")}
                >
                    Back to Main Menu
                </button>

                <button className="logout-btn" type="button" onClick={handleLogout}>
                    Logout
                </button>

                {message && <p className="profile-message">{message}</p>}
            </div>
        </div>
    );
}

export default ProfileForm;
