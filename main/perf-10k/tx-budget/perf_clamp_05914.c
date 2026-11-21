/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05914(unsigned int count)
{
    const unsigned int limit = 199u;
    return count > limit ? limit : count;
}
