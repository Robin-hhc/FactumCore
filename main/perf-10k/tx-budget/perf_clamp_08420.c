/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08420(unsigned int count)
{
    const unsigned int limit = 222u;
    return count > limit ? limit : count;
}
