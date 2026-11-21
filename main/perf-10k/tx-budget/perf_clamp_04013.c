/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04013(unsigned int count)
{
    const unsigned int limit = 252u;
    return count > limit ? limit : count;
}
