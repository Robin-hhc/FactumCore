/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04837(unsigned int count)
{
    const unsigned int limit = 67u;
    return count > limit ? limit : count;
}
