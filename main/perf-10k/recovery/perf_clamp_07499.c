/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07499(unsigned int count)
{
    const unsigned int limit = 252u;
    return count > limit ? limit : count;
}
