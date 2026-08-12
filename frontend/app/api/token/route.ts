import { NextResponse } from 'next/server';
import { execFileSync } from 'child_process';
import path from 'path';

export async function GET() {
  try {

    const scriptPath = path.resolve(process.cwd(), '../backend/src/query_escalations.py');
    const output = execFileSync('python', [scriptPath, 'list'], { encoding: 'utf-8' });
    const data = JSON.parse(output.trim() || '[]');
    return NextResponse.json({ success: true, data });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ success: false, data: [], error: message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const { id, action } = await request.json();
    if (action === 'resolve' && id) {
      const scriptPath = path.resolve(process.cwd(), '../backend/src/query_escalations.py');
      execFileSync('python', [scriptPath, 'resolve', String(id)], { encoding: 'utf-8' });
      return NextResponse.json({ success: true });
    }
    return NextResponse.json({ success: false, error: 'Invalid request' }, { status: 400 });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}
