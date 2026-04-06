import useAuth from "../../hooks/useAuth";

export default function ProfilePage() {
  const { user } = useAuth();

  const handleLogout = async () => {
    await supabase.auth.signOut();
    window.location.href = "/";
  };

  if (!user) return <div>No user found</div>;

  return (
    <div className="p-5 space-y-3">
      <h2 className="text-xl font-bold">Profile</h2>

      <p>Email: {user.email}</p>
      <p>User ID: {user.id}</p>

      <button
        onClick={handleLogout}
        className="bg-red-500 text-white px-4 py-2 rounded"
      >
        Logout
      </button>
    </div>
  );
}