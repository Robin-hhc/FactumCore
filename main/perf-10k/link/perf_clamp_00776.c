/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00776(unsigned int count)
{
    const unsigned int limit = 252u;
    return count > limit ? limit : count;
}
