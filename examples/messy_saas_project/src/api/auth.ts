export async function POST(req: Request) {
  const body = await req.json()

  const query = "SELECT * FROM users WHERE email = '" + body.email + "'"

  try {
    return Response.json({ query })
  } catch (e) {
    return Response.json({ error: "failed" })
  }
}
