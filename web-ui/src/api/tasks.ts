import type {
  Task,
  TaskCreateResponse,
  TaskGenerateRequest,
  TaskGenerationJob,
  TaskUpdate,
} from '@/types/task.d.ts'
import { http } from '@/lib/http'

export async function getAllTasks(): Promise<Task[]> {
  return await http('/api/tasks')
}

export interface TaskRunStatus {
  task_id?: number
  task_name: string
  status: 'ok' | 'empty' | 'failed' | string
  item_count: number
  finished_at: string
  error?: string | null
  reason?: string | null
  items_seen?: number
}

export async function getLastRuns(): Promise<Record<string, TaskRunStatus>> {
  const result = await http('/api/tasks/last-runs')
  return result.runs ?? {}
}

export async function createTaskWithAI(data: TaskGenerateRequest): Promise<TaskCreateResponse> {
  return await http('/api/tasks/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
}

export async function getTaskGenerationJob(jobId: string): Promise<TaskGenerationJob> {
  const result = await http(`/api/tasks/generate-jobs/${jobId}`)
  return result.job
}

export async function updateTask(taskId: number, data: TaskUpdate): Promise<Task> {
  const result = await http(`/api/tasks/${taskId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  return result.task
}

export async function startTask(taskId: number): Promise<void> {
  await http(`/api/tasks/start/${taskId}`, { method: 'POST' })
}

export async function stopTask(taskId: number): Promise<void> {
  await http(`/api/tasks/stop/${taskId}`, { method: 'POST' })
}

export async function deleteTask(taskId: number): Promise<void> {
  await http(`/api/tasks/${taskId}`, { method: 'DELETE' })
}
