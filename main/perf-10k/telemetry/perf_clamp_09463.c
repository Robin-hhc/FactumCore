/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09463(unsigned int count)
{
    const unsigned int limit = 25u;
    return count > limit ? limit : count;
}
