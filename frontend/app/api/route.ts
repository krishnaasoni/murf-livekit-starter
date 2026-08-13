import { NextResponse } from 'next/server';
import { spawnSync } from 'child_process';
import path from 'path';

function runPythonQuery(args: string[]): string {
  const scriptPath = path.resolve(process.cwd(), '../backend/src/query_escalations.py');
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
  const result = spawnSync(pythonCmd, [scriptPath, ...args], { encoding: 'utf-8' });

  if (result.error) {
    throw new Error(`Execution error: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`Process exited with code ${result.status}: ${result.stderr || ''}`);
  }
  return result.stdout ? result.stdout.trim() : '';
}

export async function GET() {
  try {
    const rawOutput = runPythonQuery(['list']);
    const data = JSON.parse(rawOutput || '[]');
    return NextResponse.json({ success: true, data });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ success: false, data: [], error: message }, { status: 200 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { id, ticket_code, action } = body || {};
    const identifier = ticket_code || id;

    if (action === 'resolve' && identifier) {
      runPythonQuery(['resolve', String(identifier)]);
      return NextResponse.json({ success: true });
    }
    return NextResponse.json(
      { success: false, error: 'Invalid request parameters' },
      { status: 400 }
    );
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ success: false, error: message }, { status: 200 });
  }
}
