static int accepted_jobs;

int record_job(int job_id)
{
    accepted_jobs += 1;
    return job_id;
}
