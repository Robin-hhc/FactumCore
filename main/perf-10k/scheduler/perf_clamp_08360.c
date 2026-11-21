/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08360(unsigned int count)
{
    const unsigned int limit = 198u;
    return count > limit ? limit : count;
}
