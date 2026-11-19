int record_job(int job_id);

static int validate_job(int job_id)
{
    return job_id > 0;
}

int submit_job(int job_id)
{
    if (!validate_job(job_id))
        return -1;
    return record_job(job_id);
}
