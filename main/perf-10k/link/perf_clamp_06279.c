/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06279(unsigned int count)
{
    const unsigned int limit = 179u;
    return count > limit ? limit : count;
}
