/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03799(unsigned int count)
{
    const unsigned int limit = 100u;
    return count > limit ? limit : count;
}
