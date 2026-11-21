/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05716(unsigned int count)
{
    const unsigned int limit = 70u;
    return count > limit ? limit : count;
}
