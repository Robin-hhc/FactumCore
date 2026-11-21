/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09193(unsigned int count)
{
    const unsigned int limit = 166u;
    return count > limit ? limit : count;
}
