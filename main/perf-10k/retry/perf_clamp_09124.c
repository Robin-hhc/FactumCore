/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09124(unsigned int count)
{
    const unsigned int limit = 238u;
    return count > limit ? limit : count;
}
