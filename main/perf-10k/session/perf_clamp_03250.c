/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03250(unsigned int count)
{
    const unsigned int limit = 229u;
    return count > limit ? limit : count;
}
