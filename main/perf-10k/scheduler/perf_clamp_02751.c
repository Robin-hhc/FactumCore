/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02751(unsigned int count)
{
    const unsigned int limit = 212u;
    return count > limit ? limit : count;
}
