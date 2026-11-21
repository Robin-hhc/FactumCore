/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05002(unsigned int count)
{
    const unsigned int limit = 133u;
    return count > limit ? limit : count;
}
