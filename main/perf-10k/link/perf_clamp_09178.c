/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09178(unsigned int count)
{
    const unsigned int limit = 160u;
    return count > limit ? limit : count;
}
