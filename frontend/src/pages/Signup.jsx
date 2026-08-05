import { useState } from "react";
import { useAuth } from "../context/AuthContext";

export default function Signup() {
  const { signUp } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const { error } = await signUp(email, password);
    if (error) {
      setError(error.message);
    } else {
      setSuccess(true); // Supabase sends a confirmation email by default
    }
  };

  if (success) {
    return <p>Check your email to confirm your account.</p>;
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>Sign up</h2>
      <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" type="email" required />
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" required />
      {error && <p style={{ color: "red" }}>{error}</p>}
      <button type="submit">Sign up</button>
    </form>
  );
}