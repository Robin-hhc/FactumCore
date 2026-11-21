/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08098(unsigned int count)
{
    const unsigned int limit = 226u;
    return count > limit ? limit : count;
}
