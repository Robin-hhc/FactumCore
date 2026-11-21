/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08541(unsigned int count)
{
    const unsigned int limit = 38u;
    return count > limit ? limit : count;
}
