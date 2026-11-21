/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09175(unsigned int count)
{
    const unsigned int limit = 109u;
    return count > limit ? limit : count;
}
