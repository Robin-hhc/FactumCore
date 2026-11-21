/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08806(unsigned int count)
{
    const unsigned int limit = 61u;
    return count > limit ? limit : count;
}
