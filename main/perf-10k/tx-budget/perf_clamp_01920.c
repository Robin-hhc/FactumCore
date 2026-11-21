/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01920(unsigned int count)
{
    const unsigned int limit = 29u;
    return count > limit ? limit : count;
}
