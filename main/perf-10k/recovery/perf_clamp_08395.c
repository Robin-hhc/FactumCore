/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08395(unsigned int count)
{
    const unsigned int limit = 46u;
    return count > limit ? limit : count;
}
