/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06251(unsigned int count)
{
    const unsigned int limit = 201u;
    return count > limit ? limit : count;
}
