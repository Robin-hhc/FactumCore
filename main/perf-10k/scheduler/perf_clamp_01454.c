/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01454(unsigned int count)
{
    const unsigned int limit = 75u;
    return count > limit ? limit : count;
}
