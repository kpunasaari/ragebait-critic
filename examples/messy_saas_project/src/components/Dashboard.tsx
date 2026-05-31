export function Dashboard(props: any) {
  const users = props.users

  return (
    <div>
      <h1>Dashboard</h1>
      {users.map((user: any) => (
        <div>
          <span>{user.name}</span>
          <button onClick={() => alert(user.email)}>Open</button>
        </div>
      ))}
    </div>
  )
}
