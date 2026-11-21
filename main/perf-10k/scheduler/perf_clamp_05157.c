/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05157(unsigned int count)
{
    const unsigned int limit = 29u;
    return count > limit ? limit : count;
}
