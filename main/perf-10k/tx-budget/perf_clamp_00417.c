/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00417(unsigned int count)
{
    const unsigned int limit = 125u;
    return count > limit ? limit : count;
}
